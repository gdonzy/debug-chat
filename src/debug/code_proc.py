import ast
import re
import time
import socket
import telnetlib
from pprint import pprint
from remote_pdb import RemotePdb

class LineVariableVisitor(ast.NodeVisitor):
    def __init__(self):
        self.variables_by_line = {}

    def visit_Attribute(self, node, attr_chain=None):
        # 递归获取完整的属性链
        if attr_chain is None:
            attr_chain = []
        attr_chain.insert(0, node.attr)
        if isinstance(node.value, ast.Attribute):
            self.visit_Attribute(node.value, attr_chain)
        elif isinstance(node.value, ast.Name):
            attr_chain.insert(0, node.value.id)
            self.record_variable(node.value.lineno, '.'.join(attr_chain))
        else:
            self.generic_visit(node)

    def visit_Name(self, node):
        # 记录简单变量的行号
        self.record_variable(node.lineno, node.id)
        self.generic_visit(node)

    def visit(self, node):
        if isinstance(node, ast.Attribute):
            self.visit_Attribute(node)
        else:
            super().visit(node)

    def record_variable(self, line_number, variable_name):
        if line_number not in self.variables_by_line:
            self.variables_by_line[line_number] = set()
        self.variables_by_line[line_number].add(variable_name)
        
def get_py_lno_vars_map(py_path):
    with open(py_path) as f:
        tree = ast.parse(f.read())

    visitor = LineVariableVisitor()
    visitor.visit(tree)
    
    return visitor.variables_by_line

