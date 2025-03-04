import os
import docker
from flask import Flask, render_template, request, redirect, url_for, session
import tempfile
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'  # 设置一个密钥，用于 session 和其他安全相关的操作 (请更换成更安全的密钥)
auth = HTTPBasicAuth()

users = {
    "admin": generate_password_hash("password")  # 示例用户名密码，请更换成更安全的方式存储
}

@auth.verify_password
def verify_password(username, password):
    if username in users and check_password_hash(users.get(username), password):
        return username
    return None

# 初始化 Docker 客户端
try:
    docker_client = docker.from_env()
    docker_client.info() # 尝试连接 Docker
except Exception as e:
    print(f"无法连接到 Docker 服务: {e}")
    docker_client = None

def get_docker_images():
    """获取 Docker 镜像列表"""
    if docker_client is None:
        return []
    images = docker_client.images.list()
    image_list = []
    for image in images:
        for tag in image.tags:
            repo_tags = tag.split(":")
            repo_name = repo_tags[0] if repo_tags else "无仓库名"
            image_tag = repo_tags[1] if len(repo_tags) > 1 else "latest"
            image_list.append({
                'id': image.short_id.replace("sha256:", ""),
                'repo_name': repo_name,
                'tag': image_tag
            })
    return image_list

def delete_docker_image(image_id):
    """删除 Docker 镜像"""
    if docker_client is None:
        return False
    try:
        image = docker_client.images.get(image_id)
        docker_client.images.remove(image.id, force=True)
        return True
    except docker.errors.ImageNotFound:
        return False
    except Exception as e:
        print(f"删除镜像 {image_id} 失败: {e}")
        return False

@app.route("/", methods=['GET', 'POST'])
@auth.login_required() # 添加登录保护
def index():
    error = None
    if request.method == 'POST':
        if 'docker_image' not in request.files:
            error = '没有上传文件'
        else:
            file = request.files['docker_image']
            if file.filename == '':
                error = '没有选择文件'
            elif file:
                if not file.filename.endswith('.tar'):
                    error = '请上传 tar 文件'
                else:
                    try:
                        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                            file.save(tmp_file.name)
                            tmp_file_path = tmp_file.name

                        if docker_client is not None:
                            with open(tmp_file_path, 'rb') as f:
                                docker_client.images.load(f)
                            os.unlink(tmp_file_path)
                            return redirect(url_for('index'))
                        else:
                            error = "无法连接到 Docker 服务，请检查 Docker 是否运行"

                    except Exception as e:
                        error = f"加载镜像失败: {e}"
                        if os.path.exists(tmp_file_path):
                            os.unlink(tmp_file_path)

    images = get_docker_images()
    return render_template('index.html', images=images, error=error, docker_connected=docker_client is not None)

@app.route('/delete_image/<image_id>')
@auth.login_required() # 添加登录保护
def delete_image_route(image_id):
    if delete_docker_image(image_id):
        return redirect(url_for('index'))
    else:
        return render_template('error.html', message=f"删除镜像 {image_id} 失败.")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=7070)