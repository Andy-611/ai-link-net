"""测试 dev-team 的提示词注入"""

import sys
from aln.app import HostClient

# 连接到 dev-team
client = HostClient(base_url="http://localhost:18000")

try:
    # 获取所有 entities
    import urllib.request
    import json

    response = urllib.request.urlopen("http://localhost:18000/entities")
    data = json.loads(response.read().decode())
    entities = data['data']

    print("=" * 80)
    print("Dev Team - Entity 信息验证")
    print("=" * 80)

    for entity in entities:
        name = entity['name']
        kind = entity['kind']
        desc_len = len(entity.get('description', ''))

        print(f"\n【{name}】")
        print(f"  Kind: {kind}")
        print(f"  Description 长度: {desc_len} 字符")
        print(f"  Address: {entity['address']['address']}")

        if kind == 'agent':
            print(f"  ✓ Agent 已注册，description 将在消息处理时注入")

    print("\n" + "=" * 80)
    print("注意：由于 handler 在消息处理时动态更新提示词，")
    print("好友信息会在第一次处理消息时自动添加到提示词中。")
    print("=" * 80)

except Exception as e:
    print(f"✗ 无法连接到 dev-team: {e}")
    print("请先运行: bash example/setup_dev_team.bash")
    sys.exit(1)
