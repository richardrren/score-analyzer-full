import subprocess
import os
import sys
import platform

def get_project_root():
    current = os.path.dirname(os.path.abspath(__file__))
    if os.path.exists(os.path.join(current, "node")):
        return current
    parent = os.path.dirname(current)
    if os.path.exists(os.path.join(parent, "node")):
        return parent
    grandparent = os.path.dirname(parent)
    if os.path.exists(os.path.join(grandparent, "node")):
        return grandparent
    return current

def get_local_node_path():
    if hasattr(sys, '_MEIPASS'):
        base_dir = sys._MEIPASS
    else:
        base_dir = get_project_root()
    
    system = platform.system()
    machine = platform.machine().lower()
    if system == "Windows":
        node_dir = os.path.join(base_dir, "node", "node-v20.10.0-win-x64")
    elif system == "Linux":
        if machine in ("aarch64", "arm64"):
            node_dir = os.path.join(base_dir, "node", "node-v20.10.0-linux-arm64")
        else:
            node_dir = os.path.join(base_dir, "node", "node-v20.10.0-linux-x64")
    else:
        node_dir = os.path.join(base_dir, "node", "node-v20.10.0-linux-x64")
    
    if os.path.exists(node_dir):
        return node_dir
    
    return None

def find_mineru_script(node_path):
    if not node_path:
        return None
    
    paths_to_check = [
        os.path.join(node_path, "lib", "node_modules", "node_modules", "mineru-open-api", "bin", "mineru-open-api"),
        os.path.join(node_path, "lib", "node_modules", "mineru-open-api", "bin", "mineru-open-api"),
        os.path.join(node_path, "node_modules", "mineru-open-api", "bin", "mineru-open-api"),
    ]
    
    for path in paths_to_check:
        if os.path.exists(path):
            return path
    
    return None

def extract_pdf_content(pdf_path):
    try:
        node_path = get_local_node_path()
        
        if not node_path:
            print("ERROR: Local Node.js not found")
            return None
        
        system = platform.system()
        if system == "Windows":
            node_exe = os.path.join(node_path, "node.exe")
        else:
            node_exe = os.path.join(node_path, "bin", "node")
        
        if not os.path.exists(node_exe):
            print(f"ERROR: Node.js executable not found at {node_exe}")
            return None
        
        mineru_script = find_mineru_script(node_path)
        if not mineru_script:
            print("ERROR: mineru-open-api script not found")
            return None
        
        cmd = [node_exe, mineru_script, "flash-extract", pdf_path]
        
        env = os.environ.copy()
        if system == "Windows":
            env["PATH"] = node_path + os.pathsep + env["PATH"]
        else:
            env["PATH"] = os.path.join(node_path, "bin") + os.pathsep + env["PATH"]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
            encoding='utf-8'
        )
        
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
        else:
            if result.stderr:
                print(f"mineru-open-api error: {result.stderr}")
            return None
            
    except subprocess.TimeoutExpired:
        print("PDF parsing timed out")
        return None
    except FileNotFoundError as e:
        print(f"ERROR: File not found - {e.filename}")
        return None
    except Exception as e:
        print(f"PDF parsing error: {e}")
        return None

if __name__ == "__main__":
    if len(sys.argv) > 1:
        pdf_file = sys.argv[1]
        print(f"Parsing: {pdf_file}")
        content = extract_pdf_content(pdf_file)
        if content:
            print(f"\nSuccess! Extracted {len(content)} characters")
            print("\nFirst 500 characters:")
            print(content[:500])
        else:
            print("Failed to parse PDF")
    else:
        print("Usage: python pdf_parser.py <pdf_file_path>")
