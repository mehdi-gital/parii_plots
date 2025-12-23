#!/usr/bin/env python3
"""
Diagrams-as-Code Compiler
Converts Mermaid templates with custom icon shorthand to rendered PNG diagrams.
"""

import argparse
import base64
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False


# Icon mapping dictionary - maps shorthand tags to local SVG paths
ICON_MAP: Dict[str, str] = {
    # AWS Icons - Compute
    "EC2": "icons/AWS_Icons/Architecture-Service-Icons_07312025/Arch_Compute/64/Arch_Amazon-EC2_64.svg",
    "LAMBDA": "icons/AWS_Icons/Architecture-Service-Icons_07312025/Arch_Compute/64/Arch_AWS-Lambda_64.svg",
    
    # AWS Icons - Database
    "AURORA": "icons/AWS_Icons/Architecture-Service-Icons_07312025/Arch_Database/64/Arch_Amazon-Aurora_64.svg",
    "DYNAMODB": "icons/AWS_Icons/Architecture-Service-Icons_07312025/Arch_Database/64/Arch_Amazon-DynamoDB_64.svg",
    "RDS": "icons/AWS_Icons/Architecture-Service-Icons_07312025/Arch_Database/64/Arch_Amazon-RDS_64.svg",
    "ELASTICACHE": "icons/AWS_Icons/Architecture-Service-Icons_07312025/Arch_Database/64/Arch_Amazon-ElastiCache_64.svg",
    
    # AWS Icons - Storage
    "S3": "icons/AWS_Icons/Architecture-Service-Icons_07312025/Arch_Storage/64/Arch_Amazon-Simple-Storage-Service_64.svg",
    
    # AWS Icons - API & Networking
    "API_GATEWAY": "icons/AWS_Icons/Architecture-Service-Icons_07312025/Arch_Networking-Content-Delivery/64/Arch_Amazon-API-Gateway_64.svg",
    "WAF": "icons/AWS_Icons/Architecture-Service-Icons_07312025/Arch_Security-Identity-Compliance/64/Arch_AWS-WAF_64.svg",
    "ACM": "icons/AWS_Icons/Architecture-Service-Icons_07312025/Arch_Security-Identity-Compliance/64/Arch_AWS-Private-Certificate-Authority_64.svg",
    
    # AWS Icons - Monitoring & Logging
    "CLOUDWATCH": "icons/AWS_Icons/Architecture-Service-Icons_07312025/Arch_Management-Governance/64/Arch_Amazon-CloudWatch_64.svg",
    "XRAY": "icons/AWS_Icons/Architecture-Service-Icons_07312025/Arch_Developer-Tools/64/Arch_AWS-X-Ray_64.svg",
    "SNS": "icons/AWS_Icons/Architecture-Service-Icons_07312025/Arch_App-Integration/64/Arch_Amazon-Simple-Notification-Service_64.svg",
    
    # AWS Icons - Security & Infrastructure
    "IAM": "icons/AWS_Icons/Architecture-Service-Icons_07312025/Arch_Security-Identity-Compliance/64/Arch_AWS-IAM-Identity-Center_64.svg",
    "VPC": "icons/AWS_Icons/Architecture-Service-Icons_07312025/Arch_Networking-Content-Delivery/64/Arch_Amazon-VPC-Lattice_64.svg",
    
    # Azure Icons - AI & Machine Learning
    "AZURE_ML": "icons/Azure_Icons/Icons/ai + machine learning/10166-icon-service-Machine-Learning.svg",
    "AZURE_AI_STUDIO": "icons/Azure_Icons/Icons/ai + machine learning/03513-icon-service-AI-Studio.svg",
    "AZURE_OPENAI": "icons/Azure_Icons/Icons/ai + machine learning/03438-icon-service-Azure-OpenAI.svg",
    "AZURE_COGNITIVE": "icons/Azure_Icons/Icons/ai + machine learning/10162-icon-service-Cognitive-Services.svg",
    "AZURE_BOT": "icons/Azure_Icons/Icons/ai + machine learning/10165-icon-service-Bot-Services.svg",
    
    # Azure Icons - Compute
    "AZURE_FUNC": "icons/Azure_Icons/Icons/compute/10029-icon-service-Function-Apps.svg",
    
    # Azure Icons - Database & Storage
    "AZURE_COSMOS": "icons/Azure_Icons/Icons/databases/10121-icon-service-Azure-Cosmos-DB.svg",
    "AZURE_STORAGE": "icons/Azure_Icons/Icons/storage/10086-icon-service-Storage-Accounts.svg",
    "AZURE_SQL": "icons/Azure_Icons/Icons/databases/02390-icon-service-Azure-SQL.svg",
    
    # Azure Icons - API & Integration
    "AZURE_API": "icons/Azure_Icons/Icons/integration/10042-icon-service-API-Management-Services.svg",
    
    # Azure Icons - Identity
    "AZURE_ENTRA": "icons/Azure_Icons/Icons/identity/02854-icon-service-Entra-Connect.svg",
    "AZURE_KEYVAULT": "icons/Azure_Icons/Icons/security/10245-icon-service-Key-Vaults.svg",
    
    # Azure Icons - Monitoring
    "AZURE_INSIGHTS": "icons/Azure_Icons/Icons/devops/00012-icon-service-Application-Insights.svg",
    "AZURE_MONITOR": "icons/Azure_Icons/Icons/monitor/00001-icon-service-Monitor.svg",
    
    # Add more icon mappings as needed
    "FOUNDRY": "icons/Azure_Icons/Icons/ai + machine learning/03513-icon-service-AI-Studio.svg",  # Using Azure AI Studio as AI Foundry
}


class MermaidCompiler:
    """Handles compilation of Mermaid diagrams with custom icon syntax."""
    
    def __init__(self, base_path: Path):
        """
        Initialize the compiler.
        
        Args:
            base_path: Base directory path for resolving relative icon paths
        """
        self.base_path = base_path
        self.temp_file = None
    
    def check_mmdc_installed(self) -> bool:
        """Check if mmdc (Mermaid CLI) is installed."""
        try:
            result = subprocess.run(
                ["mmdc", "--version"],
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode == 0:
                print(f"✓ Found mmdc: {result.stdout.strip()}")
                return True
            else:
                print("✗ Error: mmdc command failed")
                return False
        except FileNotFoundError:
            print("✗ Error: mmdc not found. Install it with: npm install -g @mermaid-js/mermaid-cli")
            return False
    
    def validate_icon_paths(self) -> bool:
        """Validate that all icon paths in the map exist."""
        all_valid = True
        for name, rel_path in ICON_MAP.items():
            abs_path = (self.base_path / rel_path).resolve()
            if not abs_path.exists():
                print(f"✗ Warning: Icon '{name}' path not found: {abs_path}")
                all_valid = False
            else:
                print(f"✓ Found icon '{name}': {abs_path}")
        return all_valid
    
    def substitute_icons(self, template_content: str) -> str:
        """
        Replace {{ICON_NAME}} placeholders with HTML img tags using base64 data URIs.
        
        Args:
            template_content: The template string with placeholders
            
        Returns:
            Processed string with img tags
        """
        def replace_tag(match):
            icon_name = match.group(1)
            if icon_name not in ICON_MAP:
                print(f"⚠ Warning: Unknown icon tag '{{{{{{icon_name}}}}}}'")
                return match.group(0)  # Return unchanged
            
            # Get absolute path to icon
            rel_path = ICON_MAP[icon_name]
            abs_path = (self.base_path / rel_path).resolve()
            
            if not abs_path.exists():
                print(f"⚠ Warning: Icon file not found: {abs_path}")
                return match.group(0)
            
            # Read SVG file and encode as base64 data URI
            try:
                with open(abs_path, 'rb') as f:
                    svg_content = f.read()
                    svg_base64 = base64.b64encode(svg_content).decode('utf-8')
                    data_uri = f"data:image/svg+xml;base64,{svg_base64}"
                
                # Generate img tag with base64 data URI
                return f'<img src="{data_uri}" width="48" height="48" />'
            except Exception as e:
                print(f"⚠ Warning: Failed to read icon {icon_name}: {e}")
                return match.group(0)
        
        # Replace all {{ICON_NAME}} patterns
        pattern = r'\{\{(\w+)\}\}'
        result = re.sub(pattern, replace_tag, template_content)
        
        return result
    
    def compile(self, input_file: Path, output_file: Path, scale: int = 3) -> bool:
        """
        Compile a Mermaid template to PNG.
        
        Args:
            input_file: Path to input .mmd file with icon placeholders
            output_file: Path to output PNG file
            scale: Scale factor for output resolution (default: 3)
            
        Returns:
            True if compilation succeeded, False otherwise
        """
        try:
            # Read the template
            print(f"\n📖 Reading template: {input_file}")
            with open(input_file, 'r', encoding='utf-8') as f:
                template_content = f.read()
            
            # Substitute icon tags
            print("🔄 Substituting icon tags...")
            processed_content = self.substitute_icons(template_content)
            
            # Write to temporary file
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.mmd',
                delete=False,
                encoding='utf-8'
            ) as tmp:
                tmp.write(processed_content)
                self.temp_file = tmp.name
            
            print(f"📝 Created temporary file: {self.temp_file}")
            
            # Run mmdc
            print(f"🎨 Rendering diagram with mmdc (scale: {scale})...")
            cmd = [
                "mmdc",
                "-i", self.temp_file,
                "-o", str(output_file),
                "-s", str(scale),
                "-b", "transparent"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode != 0:
                print(f"✗ Error running mmdc:")
                print(result.stderr)
                return False
            
            print(f"✓ Successfully generated: {output_file}")
            if result.stdout:
                print(result.stdout)
            
            return True
            
        except FileNotFoundError as e:
            print(f"✗ Error: File not found - {e}")
            return False
        except Exception as e:
            print(f"✗ Error during compilation: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            # Clean up temp file
            if self.temp_file and os.path.exists(self.temp_file):
                os.unlink(self.temp_file)
                print(f"🗑️  Cleaned up temporary file")
    
    def watch(self, input_file: Path, output_file: Path, scale: int = 3):
        """
        Watch input file for changes and recompile automatically.
        
        Args:
            input_file: Path to input .mmd file to watch
            output_file: Path to output PNG file
            scale: Scale factor for output resolution
        """
        if not WATCHDOG_AVAILABLE:
            print("✗ Error: watchdog not installed. Install it with: pip install watchdog")
            return
        
        print(f"👀 Watching {input_file} for changes... (Press Ctrl+C to stop)")
        
        # Initial compilation
        self.compile(input_file, output_file, scale)
        
        class MermaidFileHandler(FileSystemEventHandler):
            def __init__(self, compiler, input_file, output_file, scale):
                self.compiler = compiler
                self.input_file = input_file
                self.output_file = output_file
                self.scale = scale
                self.last_modified = time.time()
            
            def on_modified(self, event):
                # Only process the specific file we're watching
                if event.src_path == str(self.input_file.resolve()):
                    # Debounce - ignore events within 1 second
                    current_time = time.time()
                    if current_time - self.last_modified < 1:
                        return
                    self.last_modified = current_time
                    
                    print(f"\n🔄 Detected change in {self.input_file.name}")
                    self.compiler.compile(self.input_file, self.output_file, self.scale)
        
        event_handler = MermaidFileHandler(self, input_file, output_file, scale)
        observer = Observer()
        observer.schedule(event_handler, str(input_file.parent), recursive=False)
        observer.start()
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
            print("\n👋 Stopped watching")
        
        observer.join()


def main():
    """Main entry point for the compiler."""
    parser = argparse.ArgumentParser(
        description="Compile Mermaid diagrams with custom icon syntax to PNG",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic compilation (looks in mmd_files/ by default)
  python compiler.py input.mmd
  
  # Higher resolution
  python compiler.py input.mmd --scale 5
  
  # Watch mode (recompile on file changes)
  python compiler.py input.mmd --watch
  
  # Use custom paths
  python compiler.py /path/to/file.mmd -o /path/to/output.png
        """
    )
    
    parser.add_argument(
        "input",
        type=str,
        help="Input Mermaid file (.mmd) - will look in mmd_files/ if just filename given"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Output PNG file (default: mmd_exports/<input>.png)"
    )
    parser.add_argument(
        "-s", "--scale",
        type=int,
        default=3,
        help="Scale factor for output resolution (default: 3)"
    )
    parser.add_argument(
        "-w", "--watch",
        action="store_true",
        help="Watch input file for changes and recompile automatically"
    )
    
    args = parser.parse_args()
    
    # Resolve input file path
    input_path = Path(args.input)
    if not input_path.is_absolute() and not input_path.exists():
        # Try mmd_files directory
        mmd_dir = Path.cwd() / "mmd_files"
        potential_path = mmd_dir / args.input
        if potential_path.exists():
            input_path = potential_path
        else:
            print(f"✗ Error: Input file not found: {args.input}")
            print(f"  Tried: {input_path.resolve()}")
            print(f"  Tried: {potential_path}")
            sys.exit(1)
    elif not input_path.exists():
        print(f"✗ Error: Input file not found: {input_path}")
        sys.exit(1)
    
    # Resolve output file path
    if args.output:
        output_path = Path(args.output)
        if not output_path.is_absolute():
            # If relative, put in mmd_exports
            output_path = Path.cwd() / "mmd_exports" / args.output
    else:
        # Default: same name as input with .png extension in mmd_exports
        output_path = Path.cwd() / "mmd_exports" / input_path.stem
        output_path = output_path.with_suffix('.png')
    
    args.input = input_path
    args.output = output_path
    
    # Initialize compiler
    base_path = Path.cwd()
    compiler = MermaidCompiler(base_path)
    
    # Pre-flight checks
    print("🔍 Running pre-flight checks...")
    if not compiler.check_mmdc_installed():
        sys.exit(1)
    
    print("\n📦 Validating icon paths...")
    compiler.validate_icon_paths()
    
    # Compile or watch
    if args.watch:
        compiler.watch(args.input, args.output, args.scale)
    else:
        success = compiler.compile(args.input, args.output, args.scale)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
