import dataclasses
import pathlib
from typing import Any, Dict, List, NamedTuple, Optional, Union

import black

LINE_LENGTH = 88
BLACK_MODE = black.Mode(
    line_length=LINE_LENGTH, string_normalization=True, is_pyi=False
)


def clean_variable_name(name: str) -> str:
    """
    Clean the symbol to create a valid variable name.
    """
    return "".join(c if c.isalnum() or c in "_." else "_" for c in name)


class Variable(NamedTuple):
    name: str
    value: Any
    comment: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> List["Variable"]:
        return [cls(name=key, value=value) for key, value in data.items()]

    def generate(self) -> str:
        name = clean_variable_name(self.name)
        if self.comment:
            return f"{name} = {self.value}  # {self.comment}"
        if not isinstance(self.value, str):
            return f"{name} = {self.value}"
        try:
            return f"{name} = {float(self.value)}"
        except ValueError:
            return f"{name} = '{self.value}'"


def wrap_text(text: str, max_length: int = LINE_LENGTH) -> str:
    """
    Wrap text to ensure no line exceeds the maximum length.

    Splits lines at word boundaries if they exceed the maximum length.

    Args:
        text: The text to wrap.
        max_length: Maximum line length (default: 88 characters).

    Returns:
        The wrapped text with lines split at word boundaries.
    """
    lines = text.split("\n")
    result = []

    for line in lines:
        if len(line) <= max_length:
            result.append(line)
            continue

        current_line = ""
        words = line.split()
        for word in words:
            # Add word to current line if it fits, or start a new line
            if not current_line:
                current_line = word
            elif len(current_line) + len(word) + 1 <= max_length:
                current_line += " " + word
            else:
                result.append(current_line)
                current_line = word
        result.append(current_line)
    return "\n".join(result)


@dataclasses.dataclass
class ClassInstance:
    """
    A class instance for generating Python classes with methods and variables.
    """

    class_name: str
    base_class: str = ""
    docstring: str = ""
    class_vars: List[Variable] = dataclasses.field(default_factory=list)
    instance_vars: List[Variable] = dataclasses.field(default_factory=list)
    constructor_args: List[str] = dataclasses.field(default_factory=list)
    constructor_body: List[str] = dataclasses.field(default_factory=list)
    methods: List[str] = dataclasses.field(default_factory=list)
    has_init: bool = True


class PythonWriter:
    """A class for generating and writing Python source code files."""

    def __init__(self, base_dir: Optional[pathlib.Path] = None, indent: str = "    "):
        """
        Initialize the PythonClassWriter.

        Args:
            base_dir: Optional base directory for writing files. If None, current directory is used.
        """
        self.base_dir = base_dir if base_dir else pathlib.Path.cwd()
        self.indent_style = indent  # 4 spaces by default
        self.indent_level = 0
        self._imports = []
        self._module_variables = []
        self._classes = []

    def add_import(
        self, module: str, function: str = None, as_name: str = None
    ) -> None:
        """Add an import statement to the class."""
        statement = f"import {module}"
        if function:
            statement = f"from {module} import {function}"
        if as_name:
            statement += f" as {as_name}"
        self._imports.append(statement)

    def set_indent_style(self, use_tabs: bool = False, spaces: int = 4):
        """
        Set the indentation style.

        Args:
            use_tabs: If True, use tabs for indentation. If False, use spaces.
            spaces: Number of spaces to use for indentation if use_tabs is False.
        """
        self.indent_style = "\t" if use_tabs else " " * spaces

    def _indent(self, text: str) -> str:
        """Add proper indentation to a line of text."""
        if not text.strip():  # Don't indent empty lines
            return ""
        return self.indent_style * self.indent_level + text

    def add_class(self, class_instance: ClassInstance) -> str:
        """
        Generate a Python class definition.

        Args:
            class_instance: ClassInstance instance.

        Returns:
            String containing the formatted class definition.
        """
        result = []

        # Class definition line
        class_def = f"class {class_instance.class_name}:"
        if class_instance.base_class:
            class_def = (
                f"class {class_instance.class_name}({class_instance.base_class}):"
            )
        result.append(class_def)

        self.indent_level += 1

        # Docstring
        if class_instance.docstring:
            docstring = wrap_text(class_instance.docstring)
            if "\n" in docstring:
                newline = f"\n{self.indent_style * self.indent_level}"
                docstring = docstring.replace("\n", newline)
                docstring = f"{newline}{docstring}{newline}"
            result.append(self._indent(f'"""{docstring}"""'))

        # Class variables
        for variable in class_instance.class_vars:
            var = self._indent(variable.generate())
            if len(var) > LINE_LENGTH and variable.comment:
                result.append(self._indent(f"# {variable.comment}"))
                var = var.split("#")[0].rstrip()
            result.append(var)
        if class_instance.class_vars:
            result.append("")

        # Constructor
        if class_instance.has_init:
            args = ", ".join(["self"] + class_instance.constructor_args)
            result.append(self._indent(f"def __init__({args}):"))
            self.indent_level += 1

        # Instance variables
        for variable in class_instance.instance_vars:
            var = self._indent(f"self.{variable.generate()}")
            if len(var) > LINE_LENGTH and variable.comment:
                result.append(self._indent(f"# {variable.comment}"))
                var = var.split("#")[0].rstrip()
            result.append(var)
        if class_instance.has_init and not class_instance.instance_vars:
            result.append(self._indent("pass"))
        self.indent_level -= 1

        # Methods
        for method in class_instance.methods:
            indented = [self._indent(line) for line in method.split("\n")]
            result.append("\n" + "\n".join(indented))

        if class_instance.methods:
            self.indent_level -= 1

        self._classes.append("\n".join(result))
        return "\n".join(result)

    def generate_function(
        self,
        func_name: str,
        params: List[str] = None,
        docstring: str = None,
        implementation: str = None,
    ) -> str:
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

    def add_module_variable(self, name: str, value: str):
        """
        Add a module variable to the class.

        Args:
            name: Name of the variable.
            value: Value of the variable.
        """
        self._module_variables.append(self._indent(f"{name} = {value}"))

    def generate(self):
        output = "\n".join(self._imports) + "\n\n"
        output += "\n".join(self._module_variables) + "\n\n"
        output += "\n\n".join(self._classes) + "\n\n"
        return output

    def write(self, filepath: Union[str, pathlib.Path]) -> None:
        """
        Write content to a Python file.

        Args:
            filepath: Path to the file, relative to base_dir.
            content: Content to write to the file.
        """
        full_path = self.base_dir / pathlib.Path(filepath)
        if not full_path.parent.exists():
            full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, "w") as f:
            # f.write(black.format_str(self.generate(), mode=BLACK_MODE))
            f.write(self.generate())
            print(f"Successfully wrote {full_path}")
