import os
from os import listdir
from os.path import isfile, join
import hashlib
import shutil
import getch
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
    with open('../data/user_metadata/'+username, 'w') as f:
        f.write(str({"name": data['name'], "password": hashlib.sha224(password.encode()).hexdigest(), "tags": data['tags']}))

def change_test_owner(file_name, new_owner):
    with open('../data/test_metadata/'+file_name) as f:
        data = ast.literal_eval(f.read())
    data['owner'] = new_owner
    with open('../data/test_metadata/'+file_name, 'w') as f:
        f.write(str(data))

def migrate_data(current_username, new_username):
    os.rename('../data/user_metadata/'+current_username, '../data/user_metadata/'+new_username)
    os.rename('../data/user_data/'+current_username, '../data/user_data/'+new_username)
    created_tests = [f for f in listdir('../data/user_data/'+new_username+'/created_tests/') if isfile(join('../data/user_data/'+new_username+'/created_tests/', f))]
    for test in created_tests:
        change_test_owner(test, new_username)
    shutil.rmtree('../data/user_data/'+new_username+'/test_data')
    os.mkdir('../data/user_data/'+new_username+'/test_data')

def are_you_sure():
    while 1:
        print('Are you sure? [y/n] ')
        sure = getch.getch().lower()
        if sure == 'y':
            return True
        elif sure == 'n':
            return False
        else:
            print('Input unrecognized.\n')

if __name__ == '__main__':
    while 1:
        mode = input('Mode? [create/delete/change_password]: ')
        if mode == 'create':
            username = input('Username: ')
            password = input('Password: ')
            name = input('Name: ')
            tags = input("Tags: ")
            tags = tags.replace(' ', '').split(',')
            create(username, password, name, tags)
            print('Done.')
        elif mode == 'delete':
            username = input('Username: ')
            if are_you_sure():
                delete(username)
            else:
                print('Not modified.')
        elif mode == 'change_password':
            username = input('Username: ')
            new_password = input('New password: ')
            if are_you_sure():
                change_password(username, new_password)
                print('Done.')
            else:
                print('Not modified.')
        elif mode == 'migrate':
            username = input('Username: ')
            new_username = input('New username: ')
            if are_you_sure():
                migrate_data(username, new_username)
                print('Done.')
            else:
                print('Not modified.')
        elif mode == 'fix':
            username = input('Username: ')
            fix(username)
        else:
            print('Not recognized.')
        print()
