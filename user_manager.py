import os
from os import listdir
from os.path import isfile, join
import hashlib
import shutil
import getch
import ast
import json

def parse_dict(str_data):
    try:
        return json.loads(str_data)
    except json.decoder.JSONDecodeError:
        return ast.literal_eval(str_data)

def create(username, password, name, tags, email=""):
    if os.path.isfile('../data/user_metadata/'+username):
        return False
    with open('../data/user_metadata/'+username, 'w') as f:
        f.write(json.dumps({"name": name, "password": hashlib.sha224(password.encode()).hexdigest(), "tags": tags, "has_changed_password": False}))
    os.mkdir('../data/user_data/'+username)
    os.mkdir('../data/user_data/'+username+'/test_data')
    os.mkdir('../data/user_data/'+username+'/created_tests')
    if email != "":
        with open('../data/google_sso/'+email, 'w') as f:
            f.write(username)
        with open('../data/google_username_sso/'+username, 'w') as f:
            f.write(email)
    return True

def fix(username):
    os.mkdir('../data/user_data/'+username+'/created_tests')

def delete(username):
    shutil.rmtree('../data/user_data/'+username)
    os.remove('../data/user_metadata/'+username)
    try:
        os.remove('../data/credentials/'+username+'.pickle')
    except FileNotFoundError:
        pass
    try:
        with open('../data/google_username_sso/'+username) as f:
            email = f.read().strip()
        os.remove('../data/google_username_sso/'+username)
        os.remove('../data/google_sso/'+email)
    except FileNotFoundError:
        pass

def get(username):
    with open('../data/user_metadata/'+username) as f:
        return parse_dict(f.read())

def modify(username, password, name, tags):
    with open('../data/user_metadata/'+username, 'w') as f:
        f.write(json.dumps({"name": name, "password": hashlib.sha224(password.encode()).hexdigest(), "tags": tags}))

def change_password(username, password, reset=False):
    data = get(username)
    with open('../data/user_metadata/'+username, 'w') as f:
        if reset == False:
            f.write(json.dumps({"name": data['name'], "password": hashlib.sha224(password.encode()).hexdigest(), "tags": data['tags']}))
        elif reset == True:
            f.write(json.dumps({"name": data['name'], "password": hashlib.sha224(password.encode()).hexdigest(), "tags": data['tags'], "has_changed_password": False}))

def change_test_owner(file_name, new_owner):
    with open('../data/test_metadata/'+file_name) as f:
        data = parse_dict(f.read())
    data['owner'] = new_owner
    with open('../data/test_metadata/'+file_name, 'w') as f:
        f.write(json.dumps(data))

def migrate_data(current_username, new_username):
    os.rename('../data/user_metadata/'+current_username, '../data/user_metadata/'+new_username)
    os.rename('../data/user_data/'+current_username, '../data/user_data/'+new_username)
    created_tests = [f for f in listdir('../data/user_data/'+new_username+'/created_tests/') if isfile(join('../data/user_data/'+new_username+'/created_tests/', f))]
    for test in created_tests:
        change_test_owner(test, new_username)
    shutil.rmtree('../data/user_data/'+new_username+'/test_data')
    os.mkdir('../data/user_data/'+new_username+'/test_data')
    os.rename('../data/credentials/'+current_username+'.pickle', '../data/credentials/'+new_username+'.pickle')
    try:
        os.rename('../data/google_username_sso/'+current_username, '../data/google_username_sso/'+new_username)
    except FileNotFoundError:
        pass

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
        mode = input('Mode? [create/delete/change_password/migrate/reset_password]: ')
        if mode == 'create':
            username = input('Username: ')
            password = input('Password: ')
            name = input('Name: ')
            tags = input("Tags: ")
            tags = tags.replace(' ', '').split(',')
            email = input("Email: ").strip()
            create(username, password, name, tags, email)
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
        elif mode == 'reset_password':
            username = input('Username: ')
            new_password = input('New password: ')
            if are_you_sure():
                change_password(username, new_password, reset=True)
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
