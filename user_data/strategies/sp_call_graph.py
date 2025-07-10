import argparse
import logging
import os
import psycopg2
from psycopg2 import sql
import re
from collections import defaultdict
from consts import config  # Reuse existing database configuration

class ProcedureAnalyzer:
    def __init__(self):
        self.conn = None
        self.target_conn = None  # Add target database connection
        self.call_graph = defaultdict(list)
        self.visited = set()
        self.max_depth = 0
        self.save_dir = None

    def connect(self):
        """Establish database connection using existing config"""
        try:
            self.conn = psycopg2.connect(
                host=config['source']['host'],
                port=config['source']['port'],
                dbname=config['source']['dbname'],
                user=config['source']['user'],
                password=config['source']['password'],
                connect_timeout=10
            )
        except Exception as e:
            print(f"Database connection failed: {e}")
            raise

    # Add new method for target database connection
    def connect_target(self):
        """Establish target database connection"""
        try:
            self.target_conn = psycopg2.connect(
                host=config['destination']['host'],
                port=config['destination']['port'],
                dbname=config['destination']['dbname'],
                user=config['destination']['user'],
                password=config['destination']['password'],
                connect_timeout=10
            )
        except Exception as e:
            print(f"Target database connection failed: {e}")
            raise

    def get_procedure_definition(self, proc_name):
        """Retrieve stored procedure definition from database"""
        with self.conn.cursor() as cursor:
            cursor.execute("""
                SELECT pg_get_functiondef(p.oid)
                FROM pg_proc p
                JOIN pg_namespace n ON p.pronamespace = n.oid
                WHERE n.nspname = 'public' 
                AND proname = %s
            """, (proc_name.split('.')[-1],))  # Handle schema-qualified names
            result = cursor.fetchone()
            return result[0] if result else None

    def find_called_procedures(self, definition):
        """Find called procedures in definition using regex patterns"""
        # New: Remove comments before processing
        # Remove single-line comments (-- until end of line)
        definition = re.sub(r'--.*$', '', definition, flags=re.MULTILINE)
        # Remove multi-line comments (/*...*/)
        definition = re.sub(r'/\*.*?\*/', '', definition, flags=re.DOTALL)

        # Enhanced CALL pattern with better parameter handling
        patterns = [
            r'\bCALL\s+((?:[\w]+\.)?[\w_]+)\s*\([^\)]*\)',  # Explicit CALL statements
            r'\bEXECUTE\s+((?:[\w]+\.)?[\w_]+)\s*\b',       # EXECUTE statements
        ]
        
        # Enhanced SQL keyword list
        SQL_KEYWORDS = {
            'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'FROM', 'WHERE', 
            'JOIN', 'GROUP BY', 'ORDER BY', 'HAVING', 'LIMIT', 'OFFSET',
            'COALESCE', 'SUM', 'MAX', 'MIN', 'AVG', 'COUNT', 'FILTER'
        }

        matches = []
        for pattern in patterns:
            matches += re.findall(pattern, definition, re.IGNORECASE)

        # Modified: Maintain call order while deduplicating
        seen = set()
        valid_procedures = []
        for proc in matches:
            # Require either schema prefix or multiple components
            if '.' in proc or '_' in proc:
                # Case-insensitive keyword check
                if proc.upper() not in SQL_KEYWORDS and proc not in seen:
                    seen.add(proc)
                    valid_procedures.append(proc)

        return valid_procedures

    def build_call_graph(self, root_proc, current_depth=0):
        """Recursively build call graph with depth tracking"""
        if current_depth > 20:  # Prevent infinite recursion
            return
        if root_proc in self.visited:
            return
            
        self.visited.add(root_proc)
        self.max_depth = max(self.max_depth, current_depth)
        
        definition = self.get_procedure_definition(root_proc)
        if not definition:
            return

        # Add procedure saving logic    
        self._save_procedure_definition(root_proc, definition)
            
        called_procs = self.find_called_procedures(definition)
        for proc in called_procs:
            if '.' not in proc:  # Add schema prefix if missing
                proc = f'public.{proc}'
            self.call_graph[root_proc].append(proc)
            self.build_call_graph(proc, current_depth + 1)

    def print_results(self, root_proc, output_file=None):
        """Print hierarchical call structure with formatting and optionally save to file"""
        output = []
        output.append(f"\nCall hierarchy for {root_proc}:")
        self._build_hierarchy_output(root_proc, output)
        
        # Print to console
        print('\n'.join(output))
        
        # Save to file if specified
        if output_file:
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(output))
                logging.info(f"Call hierarchy saved to {output_file}")
            except Exception as e:
                logging.error(f"Failed to save output: {str(e)}")

    def _build_hierarchy_output(self, proc, output, level=0, last=False, prefix=''):
        """Recursive helper for building hierarchy output with ASCII art"""
        connectors = {
            'mid': '├── ',
            'end': '└── ',
            'vertical': '│   ',
            'space': '    '
        }
        
        # Current node
        line = f"{prefix}{connectors['end' if last else 'mid']}{proc}"
        output.append(line)
        
        # Children processing
        new_prefix = prefix + (connectors['vertical'] if not last else connectors['space'])
        children = self.call_graph.get(proc, [])
        for i, child in enumerate(children):
            is_last = i == len(children) - 1
            self._build_hierarchy_output(child, output, level+1, is_last, new_prefix)

    def _save_procedure_definition(self, proc_name, definition):
        """Save procedure definition to file"""
        if not self.save_dir or not definition:
            return
            
        safe_name = re.sub(r'[\\/*?:"<>|]', "_", proc_name)
        file_path = os.path.join(self.save_dir, f"{safe_name}.sql")
        try:
            logging.info(f"Starting save operation for procedure: {proc_name}")
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(definition)
            logging.info(f"Successfully saved procedure {proc_name} to {file_path}")
        except Exception as e:
            logging.error(f"Failed to save {proc_name}: {str(e)}")
            logging.debug(f"Error details:", exc_info=True)

    # Add new method to load procedures
    def load_procedures(self):
        """Load saved procedures to target database"""
        if not self.save_dir or not os.path.exists(self.save_dir):
            logging.warning(f"Load directory not found: {self.save_dir}")
            return

        logging.info(f"Starting procedure loading from directory: {self.save_dir}")
        loaded_count = 0
        
        for file_name in os.listdir(self.save_dir):
            if file_name.endswith('.sql'):
                proc_name = file_name[:-4]
                file_path = os.path.join(self.save_dir, file_name)
                logging.debug(f"Processing file: {file_path}")
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        definition = f.read()
                    logging.info(f"Loading procedure {proc_name} ({len(definition)} bytes)")
                    
                    with self.target_conn.cursor() as cursor:
                        cursor.execute(definition)
                        logging.info(f"Executed DDL for procedure {proc_name}")
                    self.target_conn.commit()
                    loaded_count += 1
                    logging.debug(f"Successfully committed transaction for {proc_name}")
                except Exception as e:
                    logging.error(f"Failed to load {proc_name}: {str(e)}")
                    logging.debug(f"Error context:", exc_info=True)
                    self.target_conn.rollback()
                    logging.debug(f"Rolled back transaction for {proc_name}")
        
        logging.info(f"Loading completed. Successfully loaded {loaded_count} procedures")

if __name__ == "__main__":
    # Add basic logging configuration
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()  # Add console handler
        ]
    )
    
    parser = argparse.ArgumentParser(description='PostgreSQL stored procedure call chain analyzer')
    parser.add_argument('procedure', help='Root stored procedure name')
    parser.add_argument('--output', type=str, help='Output file path to save call hierarchy')
    parser.add_argument('--save', action='store_true', 
                      help='Save procedure definitions to ./save/ directory')
    # Add load argument
    parser.add_argument('--load', action='store_true',
                      help='Load saved procedures to target database')
    args = parser.parse_args()

    analyzer = ProcedureAnalyzer()
    try:
        analyzer.connect()
        if args.save:
            analyzer.save_dir = os.path.abspath('./save')
            os.makedirs(analyzer.save_dir, exist_ok=True)
            logging.info(f"Initialized save directory at: {analyzer.save_dir}")
            logging.info(f"Save mode enabled, will preserve procedure definitions")
            
        analyzer.build_call_graph(args.procedure)
        analyzer.print_results(args.procedure, args.output)
        
        # Add load functionality
        if args.load:
            analyzer.connect_target()
            analyzer.load_procedures()
            logging.info("Procedure loading completed")
    except Exception as e:
        print(f"Error occurred: {str(e)}")
    finally:
        if analyzer.conn:
            analyzer.conn.close()
        if analyzer.target_conn:  # Close target connection
            analyzer.target_conn.close()