from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

from dag.expr_node import NodeType, SetNode, BagNode, TupleNode, OperatorNode, IndexedAccessNode
from dag.problem_structure import ProblemStructure
from dag.constraints import (
    CardinalityConstraint, MemberConstraint, AdjacentConstraint, TogetherConstraint,
    BeforeConstraint, SubsetConstraint, DisjointConstraint, CompositeConstraint,
    QuantifiedConstraint, ComparisonOp, IndexMemberConstraint, PredecessorConstraint,
    DedupCountConstraint, CountConstraint, IndexEqualMemberConstraint, Constraint
)


class TokenType(Enum):
    NAME = "NAME"
    NUMBER = "NUMBER"
    RANGE = "RANGE"
    PLUS = "PLUS"
    MINUS = "MINUS"
    AMPERSAND = "AMPERSAND"
    EQUALS = "EQUALS"
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    LBRACKET = "LBRACKET"
    RBRACKET = "RBRACKET"
    LBRACE = "LBRACE"
    RBRACE = "RBRACE"
    COMMA = "COMMA"
    BAR = "BAR"
    DOT = "DOT"
    COLON = "COLON"
    KW_SET = "KW_SET"
    KW_BAG = "KW_BAG"
    KW_TUPLE = "KW_TUPLE"
    KW_CHOOSE = "KW_CHOOSE"
    KW_CHOOSE_REPLACE = "KW_CHOOSE_REPLACE"
    KW_CHOOSE_TUPLE = "KW_CHOOSE_TUPLE"
    KW_CHOOSE_REPLACE_TUPLE = "KW_CHOOSE_REPLACE_TUPLE"
    KW_CHOOSE_REPLACE_SEQUENCE = "KW_CHOOSE_REPLACE_SEQUENCE"
    KW_SEQUENCE = "KW_SEQUENCE"
    KW_CIRCLE = "KW_CIRCLE"
    KW_COMPOSE = "KW_COMPOSE"
    KW_PARTITION = "KW_PARTITION"
    KW_IN = "KW_IN"
    KW_NOT = "KW_NOT"
    KW_AND = "KW_AND"
    KW_OR = "KW_OR"
    KW_TRUE = "KW_TRUE"
    KW_FALSE = "KW_FALSE"
    COMPOP = "COMPOP"
    EOF = "EOF"


KW_MAP = {
    'set': TokenType.KW_SET,
    'bag': TokenType.KW_BAG,
    'tuple': TokenType.KW_TUPLE,
    'choose': TokenType.KW_CHOOSE,
    'choose_replace': TokenType.KW_CHOOSE_REPLACE,
    'choose_tuple': TokenType.KW_CHOOSE_TUPLE,
    'choose_replace_tuple': TokenType.KW_CHOOSE_REPLACE_TUPLE,
    'choose_replace_sequence': TokenType.KW_CHOOSE_REPLACE_SEQUENCE,
    'sequence': TokenType.KW_SEQUENCE,
    'circle': TokenType.KW_CIRCLE,
    'compose': TokenType.KW_COMPOSE,
    'partition': TokenType.KW_PARTITION,
    'in': TokenType.KW_IN,
    'not': TokenType.KW_NOT,
    'and': TokenType.KW_AND,
    'or': TokenType.KW_OR,
    'True': TokenType.KW_TRUE,
    'False': TokenType.KW_FALSE,
    'reflection': TokenType.KW_TRUE,
}


@dataclass
class Token:
    type: TokenType
    value: str
    pos: int


class CofolaParseError(Exception):
    def __init__(self, message: str, pos: int = -1):
        self.pos = pos
        super().__init__(message)


class CofolaLexer:
    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.tokens: List[Token] = []

    def tokenize(self) -> List[Token]:
        self.pos = 0
        self.tokens = []
        while self.pos < len(self.source):
            self._skip_whitespace()
            if self.pos >= len(self.source):
                break
            self._tokenize_one()
        self.tokens.append(Token(TokenType.EOF, '', self.pos))
        return self.tokens

    def _skip_whitespace(self):
        while self.pos < len(self.source) and self.source[self.pos].isspace():
            self.pos += 1

    def _tokenize_one(self):
        c = self._peek(0)

        if c.isdigit():
            self._tokenize_number()
        elif c.isalpha() or c == '_':
            self._tokenize_name()
        elif c == '+':
            self.tokens.append(Token(TokenType.PLUS, c, self.pos))
            self.pos += 1
        elif c == '-':
            self.tokens.append(Token(TokenType.MINUS, c, self.pos))
            self.pos += 1
        elif c == '&':
            self.tokens.append(Token(TokenType.AMPERSAND, c, self.pos))
            self.pos += 1
        elif c == '=':
            self.tokens.append(Token(TokenType.EQUALS, c, self.pos))
            self.pos += 1
        elif c == '(':
            self.tokens.append(Token(TokenType.LPAREN, c, self.pos))
            self.pos += 1
        elif c == ')':
            self.tokens.append(Token(TokenType.RPAREN, c, self.pos))
            self.pos += 1
        elif c == '[':
            self.tokens.append(Token(TokenType.LBRACKET, c, self.pos))
            self.pos += 1
        elif c == ']':
            self.tokens.append(Token(TokenType.RBRACKET, c, self.pos))
            self.pos += 1
        elif c == '{':
            self.tokens.append(Token(TokenType.LBRACE, c, self.pos))
            self.pos += 1
        elif c == '}':
            self.tokens.append(Token(TokenType.RBRACE, c, self.pos))
            self.pos += 1
        elif c == ',':
            self.tokens.append(Token(TokenType.COMMA, c, self.pos))
            self.pos += 1
        elif c == '|':
            self.tokens.append(Token(TokenType.BAR, c, self.pos))
            self.pos += 1
        elif c == '.':
            if self._peek(1) == '.' and self._peek(2) == '.':
                self.tokens.append(Token(TokenType.RANGE, '...', self.pos))
                self.pos += 3
            else:
                self.tokens.append(Token(TokenType.DOT, c, self.pos))
                self.pos += 1
        elif c == ':':
            self.tokens.append(Token(TokenType.COLON, c, self.pos))
            self.pos += 1
        elif c == '>' or c == '<' or c == '!':
            # Comparison operators
            op = c
            if self._peek(1) == '=':
                op += '='
                self.pos += 2
            else:
                self.pos += 1
            self.tokens.append(Token(TokenType.COMPOP, op, self.pos - len(op)))
        else:
            raise CofolaParseError(f"Unexpected character '{c}'", self.pos)

    def _tokenize_name(self):
        start = self.pos
        while self.pos < len(self.source) and (self.source[self.pos].isalnum() or self.source[self.pos] == '_'):
            self.pos += 1
        value = self.source[start:self.pos]

        if value in KW_MAP:
            token_type = KW_MAP[value]
        else:
            token_type = TokenType.NAME

        self.tokens.append(Token(token_type, value, start))

    def _tokenize_number(self):
        start = self.pos
        while self.pos < len(self.source) and self.source[self.pos].isdigit():
            self.pos += 1
        value = self.source[start:self.pos]
        self.tokens.append(Token(TokenType.NUMBER, value, start))

    def _peek(self, offset: int) -> str:
        idx = self.pos + offset
        if idx < len(self.source):
            return self.source[idx]
        return ''


class CofolaParser:
    def __init__(self, source: str):
        self.lexer = CofolaLexer(source)
        self.tokens: List[Token] = []
        self.pos: int = 0
        self.bindings: Dict[str, 'ExprNode'] = {}
        self.global_constraints: List[Constraint] = []
        self.current: Optional[Token] = None

    def parse(self) -> ProblemStructure:
        self.tokens = self.lexer.tokenize()
        self.pos = 0
        self._advance()
        while self.current.type != TokenType.EOF:
            if self.current.type == TokenType.BAR:
                # Constraint on its own line (e.g., |S| >= 3)
                constraint = self._parse_constraint()
                self.global_constraints.append(constraint)
            elif self.current.type == TokenType.NAME:
                # Check what follows the NAME before consuming it
                saved_pos = self.pos
                saved_current = self.current
                self._advance()  # look ahead to next token
                if self.current.type == TokenType.EQUALS:
                    # Binding like "boys = set(...)" - restore and call _parse_binding
                    self.pos = saved_pos
                    self.current = saved_current
                    self._parse_binding()
                elif self.current.type == TokenType.KW_IN:
                    # Member constraint like "A in B" - restore and handle in constraint branch
                    self.pos = saved_pos
                    self.current = saved_current
                    element = self.current.value
                    self._advance()  # consume element
                    self._advance()  # consume 'in'
                    target_name = self._expect(TokenType.NAME)
                    c = MemberConstraint(element=element)
                    c.target = target_name
                    self.global_constraints.append(c)
                elif self.current.type == TokenType.COMPOP:
                    # Before constraint like "a < b in S" - restore and handle
                    self.pos = saved_pos
                    self.current = saved_current
                    a = self.current.value
                    self._advance()  # consume a
                    op_str = self._expect(TokenType.COMPOP)  # consume '<'
                    b = self._expect(TokenType.NAME)
                    self._expect(TokenType.KW_IN)
                    target_name = self._expect(TokenType.NAME)
                    c = BeforeConstraint(a=a, b=b)
                    c.target = target_name
                    self.global_constraints.append(c)
                elif self.current.type == TokenType.LPAREN:
                    # Could be next_to(a, b) in seq or together(a, b) in seq
                    if saved_current.value in ('next_to', 'together'):
                        # Restore and parse as adjacent/together constraint
                        self.pos = saved_pos
                        self.current = saved_current
                        constraint = self._parse_adjacent_or_together_constraint(saved_current.value)
                        self.global_constraints.append(constraint)
                    else:
                        # Not a special constraint keyword, restore and treat as constraint
                        self.pos = saved_pos
                        self.current = saved_current
                        constraint = self._parse_constraint()
                        self.global_constraints.append(constraint)
                elif self.current.type == TokenType.NAME and self.current.value in ('subset', 'disjoint'):
                    # Could be a subset/disjoint constraint like A subset set(x)
                    self.pos = saved_pos
                    self.current = saved_current
                    constraint = self._parse_constraint()
                    self.global_constraints.append(constraint)
                elif self.current.type == TokenType.DOT:
                    # Could be word.count(...) or word.dedup_count(...) constraint
                    self.pos = saved_pos
                    self.current = saved_current
                    constraint = self._parse_constraint()
                    self.global_constraints.append(constraint)
                else:
                    raise CofolaParseError(f"Unexpected token after NAME at {self.current.pos}")
            elif self.current.type == TokenType.LPAREN:
                constraint = self._parse_constraint()
                self.global_constraints.append(constraint)
            elif self.current.type == TokenType.KW_NOT:
                # Constraint like not (a in seq)
                constraint = self._parse_constraint()
                self.global_constraints.append(constraint)
            elif self.current.type == TokenType.KW_OR or self.current.type == TokenType.KW_AND:
                # Composite constraint continuation - combine with previous constraint
                op = 'or' if self.current.type == TokenType.KW_OR else 'and'
                self._advance()  # consume 'or'/'and'
                next_constraint = self._parse_constraint()
                # Combine with previous constraint if exists
                if self.global_constraints:
                    prev_constraint = self.global_constraints.pop()
                    composite = CompositeConstraint(constraints=[prev_constraint, next_constraint], operator=op)
                    self.global_constraints.append(composite)
                else:
                    # No previous constraint, just use this one
                    self.global_constraints.append(next_constraint)
            else:
                self._parse_binding()
        if not self.bindings and not self.global_constraints:
            raise CofolaParseError("No bindings found in program")
        if not self.bindings:
            # Only constraints, no bindings
            return ProblemStructure(bindings=self.bindings, root=None, global_constraints=self.global_constraints)
        root_name = list(self.bindings.keys())[-1]
        root = self.bindings[root_name]
        return ProblemStructure(bindings=self.bindings, root=root, global_constraints=self.global_constraints)

    def _advance(self):
        if self.pos < len(self.tokens):
            self.current = self.tokens[self.pos]
            self.pos += 1
        else:
            self.current = Token(TokenType.EOF, '', self.pos)

    def _expect(self, tt: TokenType, what: str = ''):
        if self.current.type != tt:
            raise CofolaParseError(f"Expected {tt} but got {self.current.type} ('{self.current.value}') at pos {self.current.pos}")
        val = self.current.value
        self._advance()
        return val

    def _parse_binding(self):
        name = self._expect(TokenType.NAME)
        if name in self.bindings:
            raise CofolaParseError(f"Duplicate binding name: {name}", self.current.pos)
        self._expect(TokenType.EQUALS)
        expr = self._parse_binary_expr()
        node = expr
        node.name = name
        self.bindings[name] = node

    def _parse_binary_expr(self) -> 'ExprNode':
        left = self._parse_primary()
        while self.current.type in (TokenType.PLUS, TokenType.AMPERSAND, TokenType.MINUS):
            op_tok = self.current
            self._advance()
            right = self._parse_primary()
            if op_tok.type == TokenType.PLUS:
                op = NodeType.SET_UNION
            elif op_tok.type == TokenType.AMPERSAND:
                op = NodeType.SET_INTERSECTION
            else:
                op = NodeType.SET_DIFFERENCE
            left = OperatorNode(operator=op, inputs=[left, right])
        return left

    def _parse_primary(self) -> 'ExprNode':
        tok = self.current
        if tok.type == TokenType.KW_SET:
            return self._parse_set_expr()
        elif tok.type == TokenType.KW_BAG:
            return self._parse_bag_expr()
        elif tok.type == TokenType.KW_TUPLE:
            return self._parse_tuple_expr()
        elif tok.type == TokenType.KW_CHOOSE:
            return self._parse_choose()
        elif tok.type == TokenType.KW_CHOOSE_REPLACE:
            return self._parse_choose_replace()
        elif tok.type == TokenType.KW_CHOOSE_TUPLE:
            return self._parse_choose_tuple()
        elif tok.type == TokenType.KW_CHOOSE_REPLACE_TUPLE:
            return self._parse_choose_replace_tuple()
        elif tok.type == TokenType.KW_CHOOSE_REPLACE_SEQUENCE:
            return self._parse_choose_replace_sequence()
        elif tok.type == TokenType.KW_SEQUENCE:
            return self._parse_sequence()
        elif tok.type == TokenType.KW_CIRCLE:
            return self._parse_circle()
        elif tok.type == TokenType.KW_COMPOSE:
            return self._parse_compose()
        elif tok.type == TokenType.KW_PARTITION:
            return self._parse_partition()
        elif tok.type == TokenType.NAME:
            name = tok.value
            self._advance()
            if self.current.type == TokenType.LBRACKET:
                return self._parse_indexed_access(name)
            node = self.bindings.get(name)
            if node is None:
                raise CofolaParseError(f"Undefined variable: {name}", tok.pos)
            return node
        elif tok.type == TokenType.LPAREN:
            self._advance()
            node = self._parse_binary_expr()
            self._expect(TokenType.RPAREN)
            return node
        else:
            raise CofolaParseError(f"Unexpected token {tok.type} at {tok.pos}")

    def _parse_set_expr(self) -> SetNode:
        self._advance()  # consume 'set'
        self._expect(TokenType.LPAREN)
        if self.current.type == TokenType.NUMBER:
            start = int(self._expect(TokenType.NUMBER))
            self._expect(TokenType.RANGE)
            stop = int(self._expect(TokenType.NUMBER))
            self._expect(TokenType.RPAREN)
            return SetNode(entitys=range(start, stop + 1))
        elif self.current.type == TokenType.NAME:
            # Check if this is a range like "boy0...6"
            name = self.current.value
            self._advance()  # consume NAME
            if self.current.type == TokenType.RANGE:
                self._advance()  # consume '...'
                stop = int(self._expect(TokenType.NUMBER))
                self._expect(TokenType.RPAREN)
                # Extract numeric suffix from name for range start
                suffix = ''.join(filter(str.isdigit, name))
                if suffix:
                    start = int(suffix)
                else:
                    start = 0
                return SetNode(entitys=range(start, stop + 1))
            else:
                # Not a range, treat as element list starting with this name
                elements = [name]
                while self.current.type == TokenType.COMMA:
                    self._advance()
                    elements.append(self._expect(TokenType.NAME))
                self._expect(TokenType.RPAREN)
                return SetNode(entitys=list(elements))
        else:
            elements = self._parse_element_list()
            self._expect(TokenType.RPAREN)
            return SetNode(entitys=list(elements))

    def _parse_bag_expr(self) -> BagNode:
        self._advance()  # consume 'bag'
        self._expect(TokenType.LPAREN)
        elements = {}
        while self.current.type != TokenType.RPAREN:
            name = self._expect(TokenType.NAME)
            if self.current.type == TokenType.COLON:
                self._advance()
                count = int(self._expect(TokenType.NUMBER))
            else:
                count = 1
            elements[name] = count
            if self.current.type == TokenType.COMMA:
                self._advance()
        self._expect(TokenType.RPAREN)
        return BagNode(entitys=elements)

    def _parse_tuple_expr(self) -> TupleNode:
        self._advance()  # consume 'tuple'
        self._expect(TokenType.LPAREN)
        elements = self._parse_element_list()
        self._expect(TokenType.RPAREN)
        return TupleNode(entitys=tuple(elements))

    def _parse_element_list(self) -> List[str]:
        result = [self._expect(TokenType.NAME)]
        while self.current.type == TokenType.COMMA:
            self._advance()
            result.append(self._expect(TokenType.NAME))
        return result

    def _parse_indexed_access(self, name: str) -> IndexedAccessNode:
        self._advance()  # consume '['
        idx = int(self._expect(TokenType.NUMBER))
        self._expect(TokenType.RBRACKET)
        parent = self.bindings.get(name)
        if parent is None:
            raise CofolaParseError(f"Undefined variable: {name}")
        return IndexedAccessNode(parent=parent, index=idx)

    # Operator parsers
    def _parse_choose(self) -> OperatorNode:
        self._advance()
        self._expect(TokenType.LPAREN)
        source = self._parse_binary_expr()
        self._expect(TokenType.COMMA)
        k = int(self._expect(TokenType.NUMBER))
        self._expect(TokenType.RPAREN)
        return OperatorNode(operator=NodeType.CHOOSE, inputs=[source], params={'k': k})

    def _parse_choose_replace(self) -> OperatorNode:
        self._advance()
        self._expect(TokenType.LPAREN)
        source = self._parse_binary_expr()
        self._expect(TokenType.COMMA)
        k = int(self._expect(TokenType.NUMBER))
        self._expect(TokenType.RPAREN)
        return OperatorNode(operator=NodeType.CHOOSE_REPLACE, inputs=[source], params={'k': k})

    def _parse_choose_tuple(self) -> OperatorNode:
        self._advance()
        self._expect(TokenType.LPAREN)
        source = self._parse_binary_expr()
        self._expect(TokenType.COMMA)
        k = int(self._expect(TokenType.NUMBER))
        self._expect(TokenType.RPAREN)
        return OperatorNode(operator=NodeType.CHOOSE_TUPLE, inputs=[source], params={'k': k})

    def _parse_choose_replace_tuple(self) -> OperatorNode:
        self._advance()
        self._expect(TokenType.LPAREN)
        source = self._parse_binary_expr()
        self._expect(TokenType.COMMA)
        k = int(self._expect(TokenType.NUMBER))
        self._expect(TokenType.RPAREN)
        return OperatorNode(operator=NodeType.CHOOSE_REPLACE_TUPLE, inputs=[source], params={'k': k})

    def _parse_choose_replace_sequence(self) -> OperatorNode:
        self._advance()
        self._expect(TokenType.LPAREN)
        source = self._parse_binary_expr()
        self._expect(TokenType.COMMA)
        k = int(self._expect(TokenType.NUMBER))
        self._expect(TokenType.RPAREN)
        return OperatorNode(operator=NodeType.CHOOSE_REPLACE_SEQUENCE, inputs=[source], params={'k': k})

    def _parse_sequence(self) -> OperatorNode:
        self._advance()
        self._expect(TokenType.LPAREN)
        source = self._parse_binary_expr()
        self._expect(TokenType.RPAREN)
        return OperatorNode(operator=NodeType.SEQUENCE, inputs=[source])

    def _parse_circle(self) -> OperatorNode:
        self._advance()
        self._expect(TokenType.LPAREN)
        source = self._parse_binary_expr()
        reflection = False
        if self.current.type == TokenType.COMMA:
            self._advance()
            self._expect(TokenType.KW_TRUE)  # reflection=True
            reflection = True
        self._expect(TokenType.RPAREN)
        return OperatorNode(operator=NodeType.CIRCLE, inputs=[source], params={'reflection': reflection})

    def _parse_compose(self) -> OperatorNode:
        self._advance()
        self._expect(TokenType.LPAREN)
        source = self._parse_binary_expr()
        self._expect(TokenType.COMMA)
        k = int(self._expect(TokenType.NUMBER))
        self._expect(TokenType.RPAREN)
        return OperatorNode(operator=NodeType.COMPOSE, inputs=[source], params={'k': k})

    def _parse_partition(self) -> OperatorNode:
        self._advance()
        self._expect(TokenType.LPAREN)
        source = self._parse_binary_expr()
        self._expect(TokenType.COMMA)
        k = int(self._expect(TokenType.NUMBER))
        self._expect(TokenType.RPAREN)
        return OperatorNode(operator=NodeType.PARTITION, inputs=[source], params={'k': k})

    # ===== Constraint Parsing Methods =====

    def _parse_constraint(self) -> Constraint:
        # Check for 'not' first
        if self.current.type == TokenType.KW_NOT:
            self._advance()
            self._expect(TokenType.LPAREN)
            inner = self._parse_constraint()
            self._expect(TokenType.RPAREN)
            return CompositeConstraint(constraints=[inner], operator='not')
        # Check for next_to(...) before LPAREN to avoid infinite recursion
        if self.current.type == TokenType.NAME and self.current.value == 'next_to':
            return self._parse_adjacent_constraint()
        # Check for together(...) before LPAREN to avoid infinite recursion
        if self.current.type == TokenType.NAME and self.current.value == 'together':
            return self._parse_together_constraint()
        # Check for composite ( ... ) — but first check if it's a predecessor constraint (a, b) in seq
        if self.current.type == TokenType.LPAREN:
            # Look ahead to check for predecessor pattern: (NAME, NAME) in NAME
            saved_pos = self.pos
            saved_current = self.current
            self._advance()  # consume '('
            if self.current.type == TokenType.NAME:
                first_name = self.current.value
                self._advance()  # consume first name
                if self.current.type == TokenType.COMMA:
                    self._advance()  # consume ','
                    if self.current.type == TokenType.NAME:
                        # This is likely a predecessor constraint (a, b) in seq
                        self.pos = saved_pos
                        self.current = saved_current
                        return self._parse_predecessor_constraint()
            # Not a predecessor constraint, restore and treat as composite
            self.pos = saved_pos
            self.current = saved_current
            self._advance()
            first = self._parse_constraint()
            parts = [first]
            while self.current.type == TokenType.KW_AND or self.current.type == TokenType.KW_OR:
                op = 'and' if self.current.type == TokenType.KW_AND else 'or'
                self._advance()
                next_c = self._parse_constraint()
                parts.append(next_c)
            self._expect(TokenType.RPAREN)
            if len(parts) == 1:
                return parts[0]
            return CompositeConstraint(constraints=parts, operator=op)
        # Check for cardinality: |expr| op NUM
        if self.current.type == TokenType.BAR:
            return self._parse_cardinality_constraint()
        # Handle or/and at top level (composite constraint continuation)
        if self.current.type == TokenType.KW_OR or self.current.type == TokenType.KW_AND:
            # This shouldn't happen at top level of _parse_constraint, but handle it
            op = 'or' if self.current.type == TokenType.KW_OR else 'and'
            self._advance()
            next_c = self._parse_constraint()
            return CompositeConstraint(constraints=[next_c], operator=op)
        # Check for name.name(...) — count or dedup_count
        if self.current.type == TokenType.NAME:
            saved_pos = self.pos
            saved_current = self.current
            name = self.current.value
            self._advance()
            if self.current.type == TokenType.DOT:
                return self._parse_method_constraint(name)
            else:
                # backup: restore both pos AND current
                self.pos = saved_pos
                self.current = saved_current

        # Otherwise: member/subset/disjoint/before constraint
        return self._parse_member_or_subset_constraint()

    def _parse_cardinality_constraint(self) -> CardinalityConstraint:
        self._expect(TokenType.BAR)  # consume '|'
        if self.current.type == TokenType.NAME:
            name = self.current.value
            self._advance()
            if self.current.type == TokenType.LBRACKET:
                self._advance()
                idx = int(self._expect(TokenType.NUMBER))
                self._expect(TokenType.RBRACKET)
                self._expect(TokenType.BAR)
                op_str = self._expect(TokenType.COMPOP)
                value = int(self._expect(TokenType.NUMBER))
                c = CardinalityConstraint(op=ComparisonOp(op_str), value=value, index=idx)
                c.target = name
                return c
            else:
                self._expect(TokenType.BAR)
                op_str = self._expect(TokenType.COMPOP)
                value = int(self._expect(TokenType.NUMBER))
                c = CardinalityConstraint(op=ComparisonOp(op_str), value=value)
                c.target = name
                return c
        else:
            raise CofolaParseError(f"Expected NAME after | at {self.current.pos}")

    def _parse_adjacent_constraint(self) -> AdjacentConstraint:
        self._advance()  # consume 'next_to'
        self._expect(TokenType.LPAREN)
        a = self._expect(TokenType.NAME)
        self._expect(TokenType.COMMA)
        b = self._expect(TokenType.NAME)
        self._expect(TokenType.RPAREN)
        self._expect(TokenType.KW_IN)
        target_name = self._expect(TokenType.NAME)
        c = AdjacentConstraint(a=a, b=b)
        c.target = target_name
        return c

    def _parse_together_constraint(self) -> TogetherConstraint:
        self._advance()  # consume 'together'
        self._expect(TokenType.LPAREN)
        members = [self._expect(TokenType.NAME)]
        while self.current.type == TokenType.COMMA:
            self._advance()
            members.append(self._expect(TokenType.NAME))
        self._expect(TokenType.RPAREN)
        self._expect(TokenType.KW_IN)
        target_name = self._expect(TokenType.NAME)
        c = TogetherConstraint(group=frozenset(members))
        c.target = target_name
        return c

    def _parse_adjacent_or_together_constraint(self, name: str) -> Constraint:
        """Parse next_to(a, b) in seq or together(a, b, c) in seq when already consumed the NAME."""
        # First consume the NAME token (next_to or together)
        self._advance()  # consume the name token
        # Now current should be LPAREN
        self._expect(TokenType.LPAREN)
        if name == 'next_to':
            a = self._expect(TokenType.NAME)
            self._expect(TokenType.COMMA)
            b = self._expect(TokenType.NAME)
            self._expect(TokenType.RPAREN)
            self._expect(TokenType.KW_IN)
            target_name = self._expect(TokenType.NAME)
            c = AdjacentConstraint(a=a, b=b)
            c.target = target_name
            return c
        else:  # together
            members = [self._expect(TokenType.NAME)]
            while self.current.type == TokenType.COMMA:
                self._advance()
                members.append(self._expect(TokenType.NAME))
            self._expect(TokenType.RPAREN)
            self._expect(TokenType.KW_IN)
            target_name = self._expect(TokenType.NAME)
            c = TogetherConstraint(group=frozenset(members))
            c.target = target_name
            return c

    def _parse_predecessor_constraint(self) -> PredecessorConstraint:
        self._expect(TokenType.LPAREN)
        a = self._expect(TokenType.NAME)
        self._expect(TokenType.COMMA)
        b = self._expect(TokenType.NAME)
        self._expect(TokenType.RPAREN)
        self._expect(TokenType.KW_IN)
        target_name = self._expect(TokenType.NAME)
        c = PredecessorConstraint(a=a, b=b)
        c.target = target_name
        return c

    def _parse_method_constraint(self, name: str) -> Constraint:
        self._advance()  # consume '.'
        method_name = self._expect(TokenType.NAME)
        if method_name == 'count':
            self._expect(TokenType.LPAREN)
            element = self._expect(TokenType.NAME)
            self._expect(TokenType.RPAREN)
            op_str = self._expect(TokenType.COMPOP)
            value = int(self._expect(TokenType.NUMBER))
            c = CountConstraint(element=element, op=ComparisonOp(op_str), value=value)
            c.target = name
            return c
        elif method_name == 'dedup_count':
            self._expect(TokenType.LPAREN)
            set_target = self._expect(TokenType.NAME)
            self._expect(TokenType.RPAREN)
            op_str = self._expect(TokenType.COMPOP)
            value = int(self._expect(TokenType.NUMBER))
            c = DedupCountConstraint(set_target=set_target, op=ComparisonOp(op_str), value=value)
            c.target = name
            return c
        else:
            raise CofolaParseError(f"Unknown method {method_name} on {name}")

    def _parse_member_or_subset_constraint(self) -> Constraint:
        left_name = self._expect(TokenType.NAME)
        # Check for (a, b) in seq — predecessor constraint
        if self.current.type == TokenType.LPAREN:
            self._advance()
            a = left_name
            b = self._expect(TokenType.NAME)
            self._expect(TokenType.RPAREN)
            self._expect(TokenType.KW_IN)
            target_name = self._expect(TokenType.NAME)
            c = PredecessorConstraint(a=a, b=b)
            c.target = target_name
            return c
        if self.current.type == TokenType.KW_IN:
            self._advance()
            target_name = self._expect(TokenType.NAME)
            c = MemberConstraint(element=left_name)
            c.target = target_name
            return c
        elif self.current.type == TokenType.COMPOP:
            # Before constraint: a < b in S
            op_str = self._expect(TokenType.COMPOP)
            right_name = self._expect(TokenType.NAME)
            self._expect(TokenType.KW_IN)
            target_name = self._expect(TokenType.NAME)
            c = BeforeConstraint(a=left_name, b=right_name)
            c.target = target_name
            return c
        elif self.current.type == TokenType.NAME and self.current.value in ('subset', 'disjoint'):
            op_name = self.current.value
            self._advance()
            if self.current.type == TokenType.KW_SET:
                self._advance()
            self._expect(TokenType.LPAREN)
            elements = self._parse_element_list()
            self._expect(TokenType.RPAREN)
            if op_name == 'subset':
                c = SubsetConstraint(target=left_name, a=','.join(elements))
                return c
            else:
                c = DisjointConstraint(target=left_name, a=','.join(elements))
                return c
        else:
            raise CofolaParseError(f"Unexpected token after {left_name}: {self.current.type}")
