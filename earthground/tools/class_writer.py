import os
import pathlib
from typing import Dict, List, Any, Optional, Union
import black

BLACK_MODE = black.Mode(
    line_length=88,
    string_normalization=True,
    is_pyi=False,
)


class PythonClassWriter:
    """A class for generating and writing Python source code files."""
    
    def __init__(self, base_dir: Optional[Union[str, pathlib.Path]] = None):
        """
        Initialize the PythonClassWriter.
        
        Args:
            base_dir: Optional base directory for writing files. If None, current directory is used.
        """
        self.base_dir = pathlib.Path(base_dir) if base_dir else pathlib.Path.cwd()
        self.indent_char = "    "  # 4 spaces by default
        self.indent_level = 0
        self.imports = []

    def add_import(self, module: str, function: str = None, as_name: str = None) -> None:
        """Add an import statement to the class."""
        statement = f"import {module}"
        if function:
            statement = f"from {module} import {function}"
        if as_name:
            statement += f" as {as_name}"
        self.imports.append(statement)
    
    def set_indent_style(self, use_tabs: bool = False, spaces: int = 4):
            self.imports.append(f"import {import_name}")
    
    def set_indent_style(self, use_tabs: bool = False, spaces: int = 4):
        """
        Set the indentation style.
        
        Args:
            use_tabs: If True, use tabs for indentation. If False, use spaces.
            spaces: Number of spaces to use for indentation if use_tabs is False.
        """
        self.indent_char = "\t" if use_tabs else " " * spaces
    
    def _indent(self, text: str) -> str:
        """Add proper indentation to a line of text."""
        if not text.strip():  # Don't indent empty lines
            return ""
        return self.indent_char * self.indent_level + text
    
    def generate_imports(self, imports: List[str]) -> str:
        """
        Generate import statements.
        
        Args:
            imports: List of import statements.
            
        Returns:
            String containing formatted import statements.
        """
        return "\n".join(imports) + "\n\n"
    
    def generate_class(self, class_name: str, base_classes: List[str] = None, 
                       docstring: str = None, methods: Dict[str, str] = None,
                       class_vars: Dict[str, Any] = None) -> str:
        """
        Generate a Python class definition.
        
        Args:
            class_name: Name of the class.
            base_classes: List of base classes.
            docstring: Class docstring.
            methods: Dictionary mapping method names to their implementations.
            class_vars: Dictionary of class variables and their values.
            
        Returns:
            String containing the formatted class definition.
        """
        result = []
        
        # Class definition line
        if base_classes:
            class_def = f"class {class_name}({', '.join(base_classes)}):"
        else:
            class_def = f"class {class_name}:"
        result.append(class_def)
        
        self.indent_level += 1
        
        # Docstring
        if docstring:
            result.append(self._indent(f'"""{docstring}"""'))
        
        # Class variables
        if class_vars:
            for var_name, value in class_vars.items():
                if isinstance(value, str):
                    result.append(self._indent(f"{var_name} = \"{value}\""))
                else:
                    result.append(self._indent(f"{var_name} = {value}"))
        
        # Methods
        if methods:
            for method_name, implementation in methods.items():
                if result and not result[-1].strip() == "":
                    result.append("")  # Add blank line before method
                result.append(self._indent(f"def {method_name}:"))
                
                # Indent the method implementation
                self.indent_level += 1
                for line in implementation.split("\n"):
                    result.append(self._indent(line))
                self.indent_level -= 1
        
        self.indent_level -= 1
        
        return "\n".join(result)
    
    def generate_function(self, func_name: str, params: List[str] = None,
                         docstring: str = None, implementation: str = None) -> str:
        """
        Generate a Python function definition.
        
        Args:
            func_name: Name of the function.
            params: List of parameter strings.
            docstring: Function docstring.
            implementation: Function implementation.
            
        Returns:
            String containing the formatted function definition.
        """
        result = []
        
        # Function definition line
        if params:
            func_def = f"def {func_name}({', '.join(params)}):"
        else:
            func_def = f"def {func_name}():"
        result.append(func_def)
        
        self.indent_level += 1
        
        # Docstring
        if docstring:
            result.append(self._indent(f'"""{docstring}"""'))
        
        # Implementation
        if implementation:
            for line in implementation.split("\n"):
                result.append(self._indent(line))
        else:
            result.append(self._indent("pass"))
        
        self.indent_level -= 1
        
        return "\n".join(result)
    
    def write_to_file(self, filepath: Union[str, pathlib.Path], content: str) -> None:
        """
        Write content to a Python file.
        
        Args:
            filepath: Path to the file, relative to base_dir.
            content: Content to write to the file.
        """
        full_path = self.base_dir / pathlib.Path(filepath)
        
        # Create directory if it doesn't exist
        os.makedirs(full_path.parent, exist_ok=True)
        
        with open(full_path, "w") as f:
            f.write(black.format_str(content, mode=BLACK_MODE))
            print(f"Successfully wrote {full_path}")
    
def create_component(path: str, attributes: Dict[str, Any], pins: List[Dict[str, str]] = None) -> None:
    """
    Create a component file with the given attributes and pins.
    
    Args:
        path: Path to write the file to.
        attributes: Dictionary of component attributes.
        pins: List of pin dictionaries with 'index', 'name', and 'comment' keys.
    """
    name = attributes.get("mpn", "component").lower()
    filepath = pathlib.Path(path) / (name + ".py")
    writer = PythonClassWriter(filepath)
    writer.add_import("earthground.components", as_name="cmp")
    writer.add_import("enum")
    
    content = "import earthground.components as cmp\n\n\n"
    content += f"class {name.upper()}(cmp.Component):\n"
    content += "    def __init__(self):\n"
    content += "        super().__init__()\n"
    
    for attr_name, value in attributes.items():
        if isinstance(value, str):
            value = f'"{value}"'
        content += f"        self.{attr_name} = {value}\n"
    
    if pins:
        content += "        self.pins = cmp.PinContainer.from_dict({\n"
        for pin in pins:
            content += " " * 12
            content += f"\"{pin['index']}\": \"{pin['name']}\""
            content += f"  # {pin['comment']},\n"
        content += "        }, self)"
    
    writer.write_to_file(filepath, content)
