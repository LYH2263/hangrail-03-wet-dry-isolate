import os

# 测试不依赖 Postgres：在导入 app 之前覆盖数据库地址（sqlite，测试内自建内存库）
os.environ.setdefault("DATABASE_URL", "sqlite://")
