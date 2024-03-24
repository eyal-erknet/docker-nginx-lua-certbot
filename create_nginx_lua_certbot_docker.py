import requests
from git import Repo
import os
import shutil
import re

MY_DOCKER_IMAGE_NAME = 'eyalerknet/nginx-lua-certbot'

BASE_PLATFORM = 'debian'
NGINX_LUA_DOCKER_IMAGE_NAME =  os.environ.get('NGINX_LUA_DOCKER_HUB_REPO', 'fabiocicerchia/nginx-lua')
NGINX_CERTBOT_GIT_NAME = os.environ.get('NGINX_CERTBOT_GIT_NAME', 'JonasAlfredsson/docker-nginx-certbot')
NGINX_CERTBOT_GIT = f'https://github.com/{NGINX_CERTBOT_GIT_NAME}.git'

BUILD_PATH = './build'
NGINX_CERTBOT_PATH = f'{BUILD_PATH}/nginx-certbot'
NGINX_CERTBOT_SRC_PATH = f'{NGINX_CERTBOT_PATH}/src'
NGINX_CERTBOT_DOCKERFILE_PATH = f'{NGINX_CERTBOT_SRC_PATH}/Dockerfile'
MODIEFIED_DOCKERFILE_FROM_LINE_FORMAT = f'FROM {NGINX_LUA_DOCKER_IMAGE_NAME}:{{tag}}'
NGINX_CERTBOT_GIT_TAG_PATTERN =  r'v([\d.]+)-nginx([\d.]+)'
VERSION_PATH = f'{BUILD_PATH}/VERSION'

docker_tags_cache = {}

def get_docker_tags(image_name, page_size = 100):
    url = f"https://hub.docker.com/v2/repositories/{image_name}/tags?page_size={page_size}"
    while True:
        tags_data = None
        if (url in docker_tags_cache):
            tags_data = docker_tags_cache[url]
        else:
            response = requests.get(url)
            if (response.status_code == 200):
                tags_data = response.json()
                docker_tags_cache[url] = tags_data
            else:
                raise Exception(f"Failed to retrieve tags for {image_name}. Status code: {response.status_code}")
        
        tags = [tag['name'] for tag in tags_data['results']]
        for tag in tags:
            yield tag
        url = tags_data['next']
        if (url is None):
            break

def clone_git_repo(url, destination):
    try:
        Repo.clone_from(url, destination)
    except Exception as e:
        raise Exception(f"Failed to clone repository from {url}: {e}")

def get_git_repo_tags(path):
    repo = Repo(path)
    tags = repo.tags
    sorted_tags = sorted(tags, key=lambda t: t.commit.committed_datetime, reverse=True)
    tag_names = [tag.name for tag in sorted_tags]
    return tag_names

def git_checkout_tag(path, tag):
    repo = Repo(path)
    repo.git.checkout(tag)

def read_file(path):
    try:
        with open(path, 'r') as file:
            return file.read()
    except FileNotFoundError as e:
        raise e
    except Exception as e:
        raise Exception(f"Error reading file '{path}': {e}")

def write_file(path, content):
    try:
        with open(path, 'w') as file:
            file.write(content)
    except Exception as e:
        raise Exception(f"Error writing to file '{path}': {e}")

def replace_first_from_line(dockerfile, from_line):
    lines = dockerfile.split('\n')
    for i, line in enumerate(lines):
        if line.strip().startswith('FROM'):
            lines[i] = from_line
            break
    return '\n'.join(lines)

def get_latest_nginx_lua_tag(nginx_version):
    tags = get_docker_tags(NGINX_LUA_DOCKER_IMAGE_NAME)
    for tag in tags:
        if ((tag.startswith(f'{nginx_version}-')) and (BASE_PLATFORM in tag)):
            return tag
    return None

def parse_nginx_certbot_tag(tag):
    match = re.match(NGINX_CERTBOT_GIT_TAG_PATTERN, tag)
    if match:
        return (match.group(1), match.group(2))
    else:
        return None

def get_latest_tags(path):
    nginx_certbot_tags = get_git_repo_tags(path)
    for nginx_certbot_tag in nginx_certbot_tags:
        nginx_version = parse_nginx_certbot_tag(nginx_certbot_tag)[1]
        if (nginx_version is not None):
            nginx_lua_tag = get_latest_nginx_lua_tag(nginx_version)
            if (nginx_lua_tag is not None):
                return (nginx_certbot_tag, nginx_lua_tag)
    raise Exception('Could not matching latest tags.')

def modify_nginx_certbot_tag(tag):
    new_from_line = MODIEFIED_DOCKERFILE_FROM_LINE_FORMAT.format(tag=tag)
    current_dockerfile = read_file(NGINX_CERTBOT_DOCKERFILE_PATH)
    new_dockerfile = replace_first_from_line(current_dockerfile, new_from_line)
    write_file(NGINX_CERTBOT_DOCKERFILE_PATH, new_dockerfile)

def create_version_tag(nginx_certbot_tag, nginx_lua_tag):
    nginx_version = parse_nginx_certbot_tag(nginx_certbot_tag)[1]
    lua_sub_tag = nginx_lua_tag[len(nginx_version)+1:]
    return f'{nginx_certbot_tag}-{lua_sub_tag}'

def get_my_latest_version():
    tags = get_docker_tags(MY_DOCKER_IMAGE_NAME)
    for tag in tags:
        if (not tag.startswith('latest')):
            return tag
    return None

if (__name__ == "__main__"):
    if (os.path.exists(NGINX_CERTBOT_PATH)):
        shutil.rmtree(NGINX_CERTBOT_PATH)
    nginx_certbot_tag = clone_git_repo(NGINX_CERTBOT_GIT, NGINX_CERTBOT_PATH)
    nginx_certbot_tag, nginx_lua_tag = get_latest_tags(NGINX_CERTBOT_PATH)
    git_checkout_tag(NGINX_CERTBOT_PATH, nginx_certbot_tag)
    modify_nginx_certbot_tag(nginx_lua_tag)
    my_latest_version = get_my_latest_version()
    build_version = create_version_tag(nginx_certbot_tag, nginx_lua_tag)
    if (my_latest_version != build_version):
        write_file(VERSION_PATH, build_version)
