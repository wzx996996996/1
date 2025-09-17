import os
import subprocess
import time
from pymongo import MongoClient
from tqdm import tqdm  # 新增：进度条库

# 连接 MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client.github
col = db.repo_with_forks

# 筛选 stars > 10 的仓库
cursor = col.find({"stars": {"$gt": 10}}, {"repo_id": 1, "html_url": 1, "stars": 1})

# 克隆保存路径
BASE_DIR = "./selected_repos"
os.makedirs(BASE_DIR, exist_ok=True)

# 分布区间统计
bins = {
    "10-100": [],
    "100-1000": [],
    "1000-10000": [],
    "10000+": []
}

# 遍历筛选 + 分类
for doc in cursor:
    repo = doc["repo_id"]
    url = doc["html_url"]
    stars = doc["stars"]

    if stars <= 100:
        bins["10-100"].append((repo, url))
    elif stars <= 1000:
        bins["100-1000"].append((repo, url))
    elif stars <= 10000:
        bins["1000-10000"].append((repo, url))
    else:
        bins["10000+"].append((repo, url))

# 打印统计
total = sum(len(v) for v in bins.values())
print(f"\n✅ 共筛选出 {total} 个 stars > 10 的仓库用于获取完整提交历史：\n")
for k, v in bins.items():
    print(f"{k:>10} ： {len(v)} 条")

# === 优化的克隆+获取完整历史函数 ===
def get_full_commits(repo_id, url, max_retries=1, retry_delay=5):
    user, name = repo_id.split("/")
    dest_path = os.path.join(BASE_DIR, user, name)

    # 检查是否已获取完整历史（通过标记文件判断）
    full_history_flag = os.path.join(dest_path, ".full_history")
    if os.path.exists(full_history_flag):
        return f"✅ 已获取完整提交历史：{repo_id}"
    if os.path.exists(dest_path):
        print(f"🔍 检测到部分克隆，尝试补全历史：{repo_id}")

    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    clone_url = f"{url}.git"

    # Git 网络配置优化
    git_config = [
        ["git", "config", "--global", "http.sslBackend", "openssl"],
        ["git", "config", "--global", "http.sslVerify", "true"],
        ["git", "config", "--global", "http.postBuffer", "1048576000"],  # 1GB 缓冲区
        ["git", "config", "--global", "transfer.retries", "3"],  # 传输重试
    ]
    for cmd in git_config:
        subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    for attempt in range(max_retries):
        try:
            # 步骤1：浅克隆（只拉取最新提交，速度快）
            if not os.path.exists(dest_path):
                print(f"⬇️  浅克隆中（第{attempt+1}/{max_retries}次）：{repo_id}")
                subprocess.run(
                    ["git", "clone", "--depth=1", clone_url, dest_path],
                    timeout=300,  # 浅克隆超时5分钟
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )

            # 步骤2：获取完整提交历史（核心步骤）
            print(f"📜 获取完整提交历史（第{attempt+1}/{max_retries}次）：{repo_id}")
            result = subprocess.run(
                ["git", "fetch", "--unshallow"],  # 取消浅克隆，获取所有历史
                cwd=dest_path,
                timeout=1800,  # 完整历史获取超时30分钟（视仓库大小调整）
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # 标记为已获取完整历史
            with open(full_history_flag, "w") as f:
                f.write("complete")
            return f"✅ 成功获取完整提交历史：{repo_id}"

        except subprocess.TimeoutExpired:
            error = "超时"
        except subprocess.CalledProcessError as e:
            error = f"命令错误：{e.stderr.strip()[:100]}"
        except Exception as e:
            error = f"未知错误：{str(e)}"

        # 清理失败的目录（如果存在）
        if os.path.exists(dest_path):
            import shutil
            shutil.rmtree(dest_path, ignore_errors=True)

        # 重试逻辑
        if attempt < max_retries - 1:
            print(f"⚠️ 第{attempt+1}次失败（{error}），{retry_delay}秒后重试...")
            time.sleep(retry_delay)
            continue

        # 记录失败的仓库
        with open("clone_failures.txt", "a") as f:
            f.write(f"{repo_id} | 原因：{error}\n")
        return f"❌ 失败（重试{max_retries}次）：{repo_id}"

# === 执行获取完整提交历史 ===
print("\n🚀 开始获取完整提交历史...\n")

# 收集所有待处理仓库（用于进度条）
all_repos = []
for group in bins.values():
    all_repos.extend(group)

try:
    # 新增：使用tqdm创建进度条，总长度为仓库总数
    for repo_id, url in tqdm(all_repos, total=len(all_repos), desc="处理进度", unit="个"):
        result = get_full_commits(repo_id, url)
        print(result)
except KeyboardInterrupt:
    print("\n⚠️ 已手动中断，下次运行将继续补全未完成的仓库")

print("\n✅ 任务结束！失败列表已保存到 clone_failures.txt")