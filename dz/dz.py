 # Конфигурационные языки
# - D2, Mermaid, PlantUML, DOT graphviz (языки описания графов)
# - XML, JSON, CSV, YAML (конф. языки общего назначения)
# - CSS, HTML (конф. языки для описания веб-страниц)
# - DSL (Domain Specific Language, предметно-ориентированные языки)
from lark import Lark, visitors
import json

grammar = r""" 
start: value+

NUM: /-?(\d+|\d+\.\d*|\.\d+)([eE][-+]?\d+)?/
NAME: /[a-zA-Z][a-zA-Z0-9]*/

assign: NAME "->" value
reference: "$[" NAME "]"
const: "set" NAME "=" value
dict: "{" (assign".")+ "}"
value: NUM | dict |const| reference

%ignore /\s/  
%ignore /#[^\n]+/        
"""

class T(visitors.Transformer):
    NUM = float
    NAME = str
    def start(self, name):
        return name
    def assign(self, name):
        return name
    def dict(self, name):
        return dict(name)
    def value(self, name):
        return name[0]
    def reference(self, name):
        return ("ref", name[0])
    def const(self, name):
        return ("const", name)

input = """
 #Это однострочный комментарий
5
50
set a = 5
{
    A -> 10.
    B -> { Z -> 10. a -> 20. r-> 30. e->$[a].}.
    C -> 5.
 }
set qq = 465
set tt = 555
"""

def interp(tree, env):
    if isinstance(tree, float):
        return tree
    if isinstance(tree, str):
        return tree
    if isinstance(tree, dict):
        output = dict()
        for k in tree:
            output[k] = interp(tree[k], env)
        return output
    if isinstance(tree, list):
        output = list()
        for i in range(len(tree)):
            output.append(interp(tree[i], env))
        return output
    if isinstance(tree, tuple):
        if tree[0] == "const":
            name = tree[1][0]
            value = tree[1][1]
            env[name] = value
            return [name, value]
        if tree[0] == "ref":
            name = tree[1]
            return env[name]

parser = Lark(grammar)
tree = parser.parse(input)
tree = T(visit_tokens=True).transform(tree)
'''print(tree)
json_ = json.dumps(tree)
print(json_)'''
tree = interp(tree, {})
json_ = json.dumps(tree)
print(json_)
