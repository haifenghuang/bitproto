"""
bitproto.renderer_base
~~~~~~~~~~~~~~~~~~~~~~~

Renderer base class and utils.
"""

import abc
import os
from typing import Dict, List, Optional, Tuple
from typing import Type as T
from typing import Union, cast

from bitproto._ast import (
    Alias,
    Array,
    Bool,
    Byte,
    Constant,
    Definition,
    Enum,
    EnumField,
    Int,
    Integer,
    Message,
    MessageField,
    Node,
    Scope,
    Proto,
    Type,
    Uint,
)
from bitproto.errors import InternalError, UnsupportedLanguageToRender

RendererClass = T["Renderer"]

BITPROTO_DECLARATION = "Code generated by bitproto. DP NOT EDIT."


def get_renderer_registry() -> Dict[str, Tuple[RendererClass, ...]]:
    """Returns the registry of language strings to renderer classes."""

    from bitproto.renderer_c import RendererC, RendererCHeader
    from bitproto.renderer_go import RendererGo
    from bitproto.renderer_py import RendererPy

    return {
        "c": (RendererC, RendererCHeader),
        "go": (RendererGo,),
        "py": (RendererPy,),
    }


def get_renderer_cls(lang: str) -> Optional[Tuple[RendererClass, ...]]:
    """Get renderer classes by language.
    """
    registry = get_renderer_registry()
    return registry.get(lang, None)


def render(proto: Proto, lang: str, outdir: Optional[str] = None) -> List[str]:
    """Render given `proto` to directory `outdir`.
    Returns the filepath list generated.
    """
    clss = get_renderer_cls(lang)
    if clss is None:
        raise UnsupportedLanguageToRender()

    outs = []
    for renderer_cls in clss:
        renderer = renderer_cls(proto, outdir=outdir)
        outs.append(renderer.render())
    return outs


class Formatter:
    """Generic language specific formatter."""

    def format_token_location(self, node: Node) -> str:
        return f"@@L{node.lineno}"

    def format_literal(self, value: Union[str, bool, int]) -> str:
        if value is True or value is False:
            return self.format_bool_literal(value)
        elif isinstance(value, str):
            return self.format_str_literal(value)
        elif isinstance(value, int):
            return self.format_int_literal(value)

    def nbits_from_integer_type(self, t: Integer) -> int:
        """Get number of bits to occupy for an given integer type in a language.
        Below is a default implementation. Special language may override this.
        """
        nbytes = t.nbytes()
        if nbytes == 1:
            return 8
        elif nbytes == 2:
            return 16
        elif nbytes in (3, 4):
            return 32
        elif nbytes in (5, 6, 7, 8):
            return 64
        return nbytes * 8

    def scopes_with_namespace(self) -> Tuple[T[Scope], ...]:
        """Returns the scope classes that define namespaces in target language.
        For example, struct in C language defines a namespace, but enum dosen't.
        For languages currently supported, the default implementation kicks enum out
        from this list. Subclasses could override.
        """
        return (Message, Proto)

    def format_definition_name(self, d: Definition) -> str:
        """Formats the declaration name for given definition in target language.
        Target languages may disallow nested declarations (such as structs, enums,
        constants, typedefs).
        Example output format: "Scope1_Scope2_{definition_name}".

        This is a default implementation, subclass may override this.
        """
        if len(d.scope_stack) == 0:
            return d.name  # Current bitproto.

        scope = d.scope_stack[-1]
        definition_name = scope.get_name_by_member(d) or d.name

        classes_ = self.scopes_with_namespace()
        namespaces = [scope for scope in d.scope_stack if isinstance(d, classes_)]

        if len(namespaces) <= 1:
            return definition_name

        namespace = namespaces[-1]

        if isinstance(namespace, Proto):  # Cross proto
            if not self.support_import():
                return definition_name
            items = [self.format_definition_name(namespace), definition_name]
            return self.delimer_cross_proto().join(items)
        else:
            items = [self.format_definition_name(namespace), definition_name]
            return self.delimer_inner_proto().join(items)

    def format_enum_name(self, t: Enum) -> str:
        """Formats the declaration name of given enum,
        with nested-declaration concern."""
        return self.format_definition_name(t)

    def format_message_name(self, t: Message) -> str:
        """Formats the declaration name of given message,
        with nested-declaration concern."""
        return self.format_definition_name(t)

    def format_alias_name(self, t: Alias) -> str:
        """Formats the declaration name of given alias,
        with nested-declaration concern."""
        return self.format_definition_name(t)

    def format_constant_name(self, v: Constant) -> str:
        """Formats the declaration name of given constant,
        with nested-declaration concern."""
        return self.format_definition_name(v)

    def format_enum_field_name(self, f: EnumField) -> str:
        """Formats the declaration name of given enum field,
        with nested-declaration concern."""
        return self.format_definition_name(f)

    def format_type(self, t: Type) -> str:
        """Formats the string representation for given type.
        This is a default implementation.
        """
        if isinstance(t, Bool):
            return self.format_bool_type()
        elif isinstance(t, Byte):
            return self.format_byte_type()
        elif isinstance(t, Uint):
            return self.format_uint_type(t)
        elif isinstance(t, Int):
            return self.format_int_type(t)
        elif isinstance(t, Array):
            return self.format_array_type(t)
        elif isinstance(t, Enum):
            return self.format_enum_type(t)
        elif isinstance(t, Message):
            return self.format_message_type(t)
        elif isinstance(t, Alias):
            return self.format_alias_type(t)
        return "_unknown_type"

    def format_left_shift(self, n: int) -> str:
        return f"<< {n}"

    def format_right_shift(self, n: int) -> str:
        return f">> {n}"

    @abc.abstractmethod
    def ident_character(self) -> str:
        """Ident character of target language, e.g. ' ', '\t'
        """
        raise NotImplementedError

    @abc.abstractmethod
    def support_import(self) -> bool:
        """Dose target language support proto import?"""
        raise NotImplementedError

    @abc.abstractmethod
    def delimer_cross_proto(self) -> str:
        """Delimer character between definitions across protos, e.g. '.'
        """
        raise NotImplementedError

    @abc.abstractmethod
    def delimer_inner_proto(self) -> str:
        """Delimer character between definitions inner a single proto, e.g. '_'
        """
        raise NotImplementedError

    @abc.abstractmethod
    def format_comment(self, content: str) -> str:
        """Format given content into a line of comment in target language."""
        raise NotImplementedError

    @abc.abstractmethod
    def format_bool_literal(self, value: bool) -> str:
        """Boolean literal representation in target language."""
        raise NotImplementedError

    @abc.abstractmethod
    def format_str_literal(self, value: str) -> str:
        """String literal representation in target language."""
        raise NotImplementedError

    @abc.abstractmethod
    def format_int_literal(self, value: int) -> str:
        """Integer literal representation in target language."""
        raise NotImplementedError

    @abc.abstractmethod
    def format_bool_type(self) -> str:
        """Bool type representation in target language."""
        raise NotImplementedError

    @abc.abstractmethod
    def format_byte_type(self) -> str:
        """Byte type representation in target language."""
        raise NotImplementedError

    @abc.abstractmethod
    def format_uint_type(self, t: Uint) -> str:
        """Unsigned integer type representation in target language."""
        raise NotImplementedError

    @abc.abstractmethod
    def format_int_type(self, t: Int) -> str:
        """Signed integer type representation in target language."""
        raise NotImplementedError

    @abc.abstractmethod
    def format_array_type(self, t: Array, name: Optional[str] = None) -> str:
        """Array type representation in target language.
        :param name: Target language (like C) may require a name for array declaration.
        """
        raise NotImplementedError

    def format_enum_type(self, t: Enum) -> str:
        """Enum type representation in target language.
        Normally the enum name, without extra declaration statements."""
        return self.format_definition_name(t)

    def format_message_type(self, t: Message) -> str:
        """Message type representation in target language.
        Normally the message name, without extra declaration statements."""
        return self.format_message_name(t)

    def format_alias_type(self, t: Alias) -> str:
        """Alias type representation in target language.
        Normally the alias name, without extra declaration statements."""
        return self.format_alias_name(t)

    @abc.abstractmethod
    def format_import_statement(self, t: Proto, as_name: Optional[str] = None) -> str:
        raise NotImplementedError


class Block:
    """Renderer block."""

    def __init__(self, formatter: Optional[Formatter] = None, ident: int = 0) -> None:
        self.strings: List[str] = []
        self._formatter: Optional[Formatter] = formatter
        self.ident = ident

    @property
    def formatter(self) -> Formatter:
        assert self._formatter is not None, InternalError("block._formatter not set")
        return self._formatter

    def set_formatter(self, formatter: Formatter) -> None:
        self._formatter = formatter

    def __str__(self) -> str:
        return "\n".join(self.strings)

    def push_string(self, s: str, separator: str = " ") -> None:
        """Append a string onto current string."""
        self.strings[-1] = separator.join([self.strings[-1], s])

    def push(self, line: str, ident: Optional[int] = None) -> None:
        """Append a line of string."""
        ident = self.ident if ident is None else ident
        if ident > 0:
            line = ident * self.formatter.ident_character() + line
        self.strings.append(line)

    def push_empty_line(self) -> None:
        self.push("")

    def clear(self) -> None:
        self.strings = []

    def collect(self) -> str:
        s = str(self)
        self.clear()
        return s

    @abc.abstractmethod
    def render(self) -> None:
        """Render processor for this block, invoked by Renderer.render()."""
        raise NotImplementedError

    def defer(self) -> None:
        """Defer render processor for this block. invoked by Renderer.render()."""
        raise NotImplementedError


class BlockForDefinition(Block):
    """Block for definition."""

    def __init__(
        self,
        definition: Definition,
        name: Optional[str] = None,
        formatter: Optional[Formatter] = None,
        ident: int = 0,
    ) -> None:
        super(BlockForDefinition, self).__init__(formatter=formatter, ident=ident)

        self.definition = definition
        self.definition_name: str = name or definition.name

    @property
    def as_constant(self) -> Constant:
        return cast(Constant, self.definition)

    @property
    def as_alias(self) -> Alias:
        return cast(Alias, self.definition)

    @property
    def as_enum(self) -> Enum:
        return cast(Enum, self.definition)

    @property
    def as_enum_field(self) -> EnumField:
        return cast(EnumField, self.definition)

    @property
    def as_message(self) -> Message:
        return cast(Message, self.definition)

    @property
    def as_message_field(self) -> MessageField:
        return cast(MessageField, self.definition)

    @property
    def as_proto(self) -> Proto:
        return cast(Proto, self.definition)

    def render_doc(self) -> None:
        for comment in self.definition.comment_block:
            self.push(self.formatter.format_comment(comment.content()))

    def push_location_doc(self) -> None:
        """Push current definition source location as an inline-comment to current line."""
        location_string = self.formatter.format_token_location(self.definition)
        self.push_string(self.formatter.format_comment(location_string), separator=" ")


class Renderer:
    """Base renderer class.

    :param proto: The parsed bitproto instance.
    :param outdir: The directory to write files, defaults to the source
       bitproto's file directory, or cwd.
    """

    def __init__(self, proto: Proto, outdir: Optional[str] = None) -> None:
        self.proto = proto
        self.outdir = outdir or self.get_outdir_default(proto)

        self.out_filename = self.format_out_filename()
        self.out_filepath = os.path.join(self.outdir, self.out_filename)

    def get_outdir_default(self, proto: Proto) -> str:
        """Returns outdir default.
        If the given proto is parsed from a file, then use the its directory.
        Otherwise, use current working directory.
        """
        if proto.filepath:  # Parsing from a file.
            return os.path.dirname(os.path.abspath(proto.filepath))
        return os.getcwd()

    def format_out_filename(self) -> str:
        """Returns the output file's name for given extension.

            >>> format_out_filepath(".go")
            example_bp.go
        """
        out_base_name = self.proto.name
        if self.proto.filepath:
            proto_base_name = os.path.basename(self.proto.filepath)
            out_base_name = os.path.splitext(proto_base_name)[0]  # remove extension
        out_filename = out_base_name + "_bp" + self.file_extension()
        return out_filename

    def render_string(self) -> str:
        """Render current proto to string."""
        blocks = self.blocks()
        strings = []
        formatter = self.formatter()

        # Sets formatter
        for block in blocks:
            block.set_formatter(formatter)

        # Executes `render()`.
        for block in blocks:
            block.render()
            strings.append(block.collect())

        # Executes `defer()`.
        reversed_blocks = blocks[::-1]
        for block in reversed_blocks:
            try:
                block.defer()
                strings.append(block.collect())
            except NotImplementedError:
                pass
        return "\n\n".join(strings)

    def render(self) -> str:
        """Render current proto to file(s).
        Returns the filepath generated.
        """
        content = self.render_string()

        with open(self.out_filepath, "w") as f:
            f.write(content)
        return self.out_filepath

    @abc.abstractmethod
    def blocks(self) -> List[Block]:
        """Returns the blocks to render."""
        raise NotImplementedError

    @abc.abstractmethod
    def file_extension(self) -> str:
        """Returns the file extension to generate.  e.g. ".c"
        """
        raise NotImplementedError

    @abc.abstractmethod
    def formatter(self) -> Formatter:
        raise NotImplementedError
