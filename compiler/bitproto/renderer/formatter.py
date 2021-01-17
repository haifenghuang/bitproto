"""
bitproto.renderer.formatter
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Formatter class base.
"""
import os
from abc import abstractmethod
from enum import Enum as Enum_
from enum import unique
from typing import Callable, Dict, List, Optional, Tuple
from typing import Type as T
from typing import TypeVar, Union, cast

from bitproto._ast import (Alias, Array, Bool, BooleanConstant, BoundScope,
                           Byte, Constant, Definition, Enum, EnumField, Int,
                           Integer, IntegerConstant, Message, MessageField,
                           Node, Proto, Scope, SingleType, StringConstant,
                           Type, Uint, Value)
from bitproto.errors import InternalError
from bitproto.utils import (final, keep_case, overridable, pascal_case,
                            snake_case, upper_case)

CaseStyleConverter = Callable[[str], str]

# Dict[DefinitionType => One or tuple of CaseStyle name OR CaseStyleConverter]
CaseStyleMapping = Dict[T[Definition], Union[str, Tuple[str, ...], CaseStyleConverter]]


@unique
class CaseStyle(Enum_):

    KEEP = 0
    SNAKE = 1
    UPPER = 2
    PASCAL = 3

    def converter(self) -> CaseStyleConverter:
        """Returns the case converter function."""
        if self is self.SNAKE:
            return snake_case
        elif self is self.UPPER:
            return upper_case
        elif self is self.PASCAL:
            return pascal_case
        return keep_case

    @classmethod
    def from_name(cls, name: str) -> "CaseStyle":
        mapping = {
            "snake": cls.SNAKE,
            "upper": cls.UPPER,
            "pascal": cls.PASCAL,
        }
        return mapping.get(name, cls.KEEP)


class Formatter:
    """Generic language specific formatter."""

    # Abstracts

    @abstractmethod
    def case_style_mapping(self) -> CaseStyleMapping:
        """Returns the case style mapping for target language.
        Example for C language:

            {
                Constant: "upper",
                EnumField: ("snake", "upper"),  # apply one by one
            }
        """
        raise NotImplementedError

    @abstractmethod
    def indent_character(self) -> str:
        """Indent character of target language."""
        raise NotImplementedError

    @abstractmethod
    def support_import_as_member(self) -> bool:
        """Dose target language support importing a proto as another proto's member?
        As we know, C language dosen't.
        """
        raise NotImplementedError

    @abstractmethod
    def format_import_statement(self, t: Proto, as_name: Optional[str] = None) -> str:
        """Format import statement.
        :param t: The proto to import.
        :param as_name: The name of the member to import as.
        """
        raise NotImplementedError

    @abstractmethod
    def format_comment(self, content: str) -> str:
        """Format given content into a line of comment in target language."""
        raise NotImplementedError

    @abstractmethod
    def format_bool_value(self, value: bool) -> str:
        """Boolean literal representation in target language."""
        raise NotImplementedError

    @abstractmethod
    def format_str_value(self, value: str) -> str:
        """String literal representation in target language."""
        raise NotImplementedError

    @abstractmethod
    def format_int_value(self, value: int) -> str:
        """Integer literal representation in target language."""
        raise NotImplementedError

    @abstractmethod
    def format_bool_type(self) -> str:
        """Bool type representation in target language."""
        raise NotImplementedError

    @abstractmethod
    def format_byte_type(self) -> str:
        """Byte type representation in target language."""
        raise NotImplementedError

    @abstractmethod
    def format_uint_type(self, t: Uint) -> str:
        """Unsigned integer type representation in target language."""
        raise NotImplementedError

    @abstractmethod
    def format_int_type(self, t: Int) -> str:
        """Signed integer type representation in target language."""
        raise NotImplementedError

    @abstractmethod
    def format_array_type(self, t: Array, name: Optional[str] = None) -> str:
        """Array type representation in target language.
        :param name: Target language (like C) may require a name for array declaration.
        """
        raise NotImplementedError

    # Overridables

    @overridable
    def format_left_shift(self, n: int) -> str:
        """Returns the representation to shift left for n bits."""
        return f"<< {n}"

    @overridable
    def format_right_shift(self, n: int) -> str:
        """Returns the representation to shift right for n bits."""
        return f">> {n}"

    @overridable
    def format_docstring(self, *comments: str) -> List[str]:
        """Format given lines of comments to a list of docstring lines.
        Default implemented to lines of comments.
        """
        return [self.format_comment(comment) for comment in comments]

    @overridable
    def format_int_value_type(self) -> str:
        """Returns the type representation in target language for a integer value."""
        raise NotImplementedError

    @overridable
    def format_string_value_type(self) -> str:
        """Returns the type representation in target language for a string value."""
        raise NotImplementedError

    @overridable
    def format_bool_value_type(self) -> str:
        """Returns the type representation in target language for a bool value."""
        raise NotImplementedError

    @overridable
    def format_enum_type(self, t: Enum) -> str:
        """Enum type representation in target language.
        Without extra declaration statements.
        Normally the enum name."""
        return self.format_definition_name(t)

    @overridable
    def format_message_type(self, t: Message) -> str:
        """Message type representation in target language.
        Without extra declaration statements.
        Normally the message name."""
        return self.format_message_name(t)

    @overridable
    def format_alias_type(self, t: Alias) -> str:
        """Alias type representation in target language.
        Without extra declaration statements
        Normally the alias name."""
        return self.format_alias_name(t)

    @overridable
    def delimer_cross_proto(self) -> str:
        """Delimer character between definitions across protos, e.g. '.'
        This delimer would be used to join name between proto and its member definitions.
        For target languages that dosen't support `import as`, this delimer is useless and
        this function won't be accessed.
        """
        return "."

    @overridable
    def delimer_inner_proto(self) -> str:
        """Delimer character between definitions inner a single proto, e.g. '_'
        This delimer would be used to join name between scope and its member definitions.
        By default, it's underscore, which adapts a lot of target languages.
        """
        return "_"

    @overridable
    def scopes_with_namespace(self) -> Tuple[T[Scope], ...]:
        """Returns the scope classes that define namespaces in target language.
        For example, struct in C language defines a namespace, but enum dosen't.
        For languages currently supported, the default implementation kicks enum out
        from this list. Subclasses could override.
        """
        return (Message, Proto)

    # Finals

    @final
    def format_token_location(self, node: Node) -> str:
        """Format the source location mark for given node."""
        return f"@@L{node.lineno}"

    @final
    def format_value(self, value: Value) -> str:
        """Format value to its string representation."""
        if value is True or value is False:
            return self.format_bool_value(value)
        elif isinstance(value, str):
            return self.format_str_value(value)
        elif isinstance(value, int):
            return self.format_int_value(value)

    @overridable
    def get_nbits_of_integer(self, t: Integer) -> int:
        """Get number of bits to occupy for an given integer type in a language.
        Special language may override this default implementation.
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

    def _get_definition_name(self, d: Definition) -> str:
        """Get definition name, name defined in its scope or its original name."""
        if len(d.scope_stack) <= 0:
            return d.name
        scope = d.scope_stack[-1]
        return scope.get_name_by_member(d) or d.name

    def _format_definition_name_inner_proto(self, d: Definition) -> str:
        """Formats the declaration name for given definition in target language inner a
        proto. Target languages may disallow nested declarations (such as structs, enums,
        constants, typedefs), so we join the names of the definition's parent namespace
        scopes with underscore. Example output format: "Scope1_Scope2_{definition_name}".
        """
        definition_name = self._get_definition_name(d)

        classes_ = self.scopes_with_namespace()
        namespaces = [scope for scope in d.scope_stack if isinstance(scope, classes_)]

        if len(namespaces) <= 1:
            return definition_name  # Global definition.

        items: List[str] = [definition_name]

        for namespace in namespaces[::-1]:  # Assuming its bound at last.
            if isinstance(namespace, BoundScope):
                items.insert(0, self._get_definition_name(namespace))
            elif isinstance(namespace, Proto):
                break
        return self.delimer_inner_proto().join(items)

    def format_definition_name_inner_proto(
        self, d: Definition, class_: Optional[T[Definition]] = None
    ) -> str:
        """`_format_definition_name_inner_proto` with case style converting."""
        class_ = class_ or d.__class__
        name = self._format_definition_name_inner_proto(d)
        return self.format_case_style(name, class_)

    @final
    def format_case_style(self, s: str, class_: T[Definition]) -> str:
        """Format given string s by case converting of class_, using the
        case_style_mapping.
        """
        mapping = self.case_style_mapping()
        v = mapping.get(class_, "keep")

        if isinstance(v, str):
            case_style_name = cast(str, v)
            case_style = CaseStyle.from_name(case_style_name)
            converter = case_style.converter()
            return converter(s)
        elif isinstance(v, tuple):
            case_style_names = cast(Tuple[str, ...], v)
            for case_style_name in case_style_names:
                case_style = CaseStyle.from_name(case_style_name)
                converter = case_style.converter()
                s = converter(s)
            return s
        elif callable(v):
            converter = cast(CaseStyleConverter, v)
            return converter(s)
        else:
            raise InternalError(f"invalid case_style mapping value {v}")

    @final
    def format_definition_name(
        self, d: Definition, class_: Optional[T[Definition]] = None
    ) -> str:
        """Formats the declaration name for given definition in target language.
        Joins a with a dot delimer if given definition is a definition imported.
        """
        definition_name = self.format_definition_name_inner_proto(d, class_)
        protos = [scope for scope in d.scope_stack if isinstance(scope, Proto)]

        if len(protos) <= 1:
            return definition_name

        if not self.support_import_as_member():
            return definition_name

        proto = protos[-1]  # Last is the imported parent.
        items = [self._get_definition_name(proto), definition_name]
        return self.delimer_cross_proto().join(items)

    @final
    def format_name_related_to_definition(
        self, d: Definition, fmt: str, class_: Optional[T[Definition]] = None
    ) -> str:
        """Format a name related to given definition d from given formatter fmt.
        Example fmt: 'XXX{definition_name}'.
        Output format: {proto}.XXX{definition_name}
        """
        definition_name = self.format_definition_name_inner_proto(d, class_)
        formatted_name = fmt.format(definition_name=definition_name)
        protos = [scope for scope in d.scope_stack if isinstance(scope, Proto)]
        if len(protos) <= 1:
            return formatted_name

        if not self.support_import_as_member():
            return formatted_name

        proto = protos[-1]  # Last is the imported parent.
        items = [self._get_definition_name(proto), formatted_name]
        return self.delimer_cross_proto().join(items)

    @final
    def format_enum_name(self, t: Enum) -> str:
        """Formats the declaration name of given enum,
        with nested-declaration concern."""
        return self.format_definition_name(t, Enum)

    @final
    def format_message_name(self, t: Message) -> str:
        """Formats the declaration name of given message,
        with nested-declaration concern."""
        return self.format_definition_name(t)

    @final
    def format_alias_name(self, t: Alias) -> str:
        """Formats the declaration name of given alias,
        with nested-declaration concern."""
        return self.format_definition_name(t)

    @final
    def format_constant_name(self, v: Constant) -> str:
        """Formats the declaration name of given constant,
        with nested-declaration concern."""
        return self.format_definition_name(v)

    @final
    def format_enum_field_name(self, f: EnumField) -> str:
        """Formats the declaration name of given enum field,
        with nested-declaration concern."""
        return self.format_definition_name(f)

    @final
    def format_message_field_name(self, f: MessageField) -> str:
        """Formats the declaration name of given message field."""
        return self.format_case_style(f.name, MessageField)

    @final
    def format_type(self, t: Type, name: Optional[str] = None) -> str:
        """Formats the string representation for given type.
        This is a default implementation.

        :param name: The name helps to build the type's representation.
            Currently, only `format_array_type` takes this argument forward.
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
            return self.format_array_type(t, name=name)
        elif isinstance(t, Enum):
            return self.format_enum_type(t)
        elif isinstance(t, Message):
            return self.format_message_type(t)
        elif isinstance(t, Alias):
            return self.format_alias_type(t)
        raise InternalError("unknown type for format_type")

    @final
    def format_constant_type(self, c: Constant) -> str:
        """Formats the string representation for given constant's type."""
        if isinstance(c, BooleanConstant):
            return self.format_bool_value_type()
        elif isinstance(c, StringConstant):
            return self.format_string_value_type()
        elif isinstance(c, IntegerConstant):
            return self.format_int_value_type()
        raise InternalError(f"got unexpected constant type {c}")

    @final
    def format_out_filename(self, proto: Proto, extension: str) -> str:
        """Formats the out file name for given proto and given extension.

            >>> format_out_filename(proto, ".h")
            "example_bp.h"
        """
        out_base_name = proto.name
        if proto.filepath:
            proto_base_name = os.path.basename(proto.filepath)
            out_base_name = os.path.splitext(proto_base_name)[0]  # remove extension
        out_filename = out_base_name + "_bp" + extension
        return out_filename


F = TypeVar("F", bound=Formatter)