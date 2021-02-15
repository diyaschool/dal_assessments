import os
import hashlib
import shutil
import ast

def create(username, password, name, tags):
    if os.path.isfile('../data/user_metadata/'+username):
        return False
    with open('../data/user_metadata/'+username, 'w') as f:
        f.write(str({"name": name, "password": hashlib.sha224(password.encode()).hexdigest(), "tags": tags, "has_changed_password": False}))
    os.mkdir('../data/user_data/'+username)
    os.mkdir('../data/user_data/'+username+'/test_data')
    os.mkdir('../data/user_data/'+username+'/created_tests')
    return True

def fix(username):
    os.mkdir('../data/user_data/'+username+'/created_tests')

def delete(username):
    shutil.rmtree('../data/user_data/'+username)
    os.remove('../data/user_metadata/'+username)

def get(username):
    with open('../data/user_metadata/'+username) as f:
        return ast.literal_eval(f.read())

def modify(username, password, name, tags):
    with open('../data/user_metadata/'+username, 'w') as f:
        f.write(str({"name": name, "password": hashlib.sha224(password.encode()).hexdigest(), "tags": tags}))

def change_password(username, password):
    data = get(username)
    print(data)
    print(password)
    with open('../data/user_metadata/'+username, 'w') as f:
        f.write(str({"name": data['name'], "password": hashlib.sha224(password.encode()).hexdigest(), "tags": data['tags']}))

if __name__ == '__main__':
    while 1:
        mode = input('Mode? [create/delete/get/modify]: ')
        if mode == 'create':
            username = input('Username: ')
            password = input('Password: ')
            name = input('Name: ')
            tags = input("Tags: ")
            tags = tags.split(',')
            create(username, password, name, tags)
            print('Done.\n')
        elif mode == 'delete':
            username = input('Username: ')
            sure = input('Are you sure? [y/N]: ').lower()
            if sure == 'n':
                print('Not modified.\n')
            elif sure == 'y':
                delete(username)
            else:
                print('Not recognized.\n')
        elif mode == 'fix':
            username = input('Username: ')
            fix(username)
        else:
            print('Not recognized.\n')
