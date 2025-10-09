import os

def exp(a:str):
    for k in os.environ:
        a=a.replace("$"+k,os.environ[k])

while True:
    a=input("VFS ")
    b=a.split()
    if a == "exit":
        break
    elif len(a)==0:
        continue
    elif b[0]=='ls':
        print('ls')
    elif b[0]=="cd":
        print('cd')
    elif b[0]=="echo":
        a=exp(a)
        print(a)
    else:
        print('CommandNotFoundException')
