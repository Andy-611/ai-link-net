# TODO: Market 支持跨 Host Entity 发布订单

> 状态：待实现
>
> 优先级：中（当前 demo 用 Arbiter 代发 workaround，功能可用但语义不正确）

## 1. 问题描述

当前 Market 的 `publish_order` API 要求 publisher entity 必须注册在 Arbiter 所在的 Host 上。
跨 Host 的 Entity（如 child-a 上的 Coder）无法直接向 Market 发布 supply 订单。

**现象**：
`aln market publish -e <child-host-entity-addr> --type supply ...` 发布失败，
API 返回 404: `Entity not found`。

**根因**：调用链中 `resolve_sender_entity` 只在 Arbiter 本机查找 entity，
不支持跨 Host 解析。


## 2. 当前调用链分析

```
CLI                              API (Arbiter Host)
────                             ─────────────────
1. resolve_entity_card(spec)     
   → 在 entity 所在 host 上      
     查到 EntityCard ✓           
                                 
2. resolve_arbiter_client(card)  
   → 找到 Arbiter 所在 host ✓    
                                 
3. payload = {                   
     "publisher": card.entity_uid  ← 只传了 entity_uid
   }                             
   client.market_publish(payload)
                                 4. resolve_sender_entity(current_host, publisher)
                                    → host.get_entity(entity_uid)
                                    → 只在 Arbiter Host 本地查找 ✗
                                    → 404 Entity not found
                                 
                                 5. address = f"{current_host.uid}:{entity.uid}"
                                    → 即使找到，地址也会拼成 Arbiter Host 的，不是源 Host 的
```

### 涉及文件

| 文件 | 位置 | 问题 |
|------|------|------|
| `aln/cli/market.py:87-91` | CLI publish_command | payload 只传 `entity_uid`，丢失了 host 信息 |
| `aln/app/schemas/market.py:47` | PublishOrderRequest.publisher | 字段类型是 `str`，只存 entity_uid |
| `aln/app/api/v1/trade.py:374` | publish_order handler | `resolve_sender_entity` 只查本机 |
| `aln/app/misc/common.py:17-27` | resolve_sender_entity | 只查 `host.get_entity()`，无跨 Host 能力 |
| `aln/app/api/v1/trade.py:375` | address 拼接 | 硬编码 `current_host.uid`，跨 Host 地址会错 |


## 3. 修改方案

核心思路：**CLI 传完整 FPAddress，API 信任 CLI 已验证的身份，
Arbiter 只做存储不做发布者身份校验**（发布者身份校验由 CLI 侧完成）。

### 3.1 修改 PublishOrderRequest（schemas）

```python
# aln/app/schemas/market.py

class PublishOrderRequest(BaseModel):
    order_type: OrderType
    publisher: str = Field(description="Publisher entity_uid")
    publisher_address: str = Field(description="Full FPAddress (host_uid:entity_uid)")  # 新增
    title: str
    description: str = ""
    budget: float | None = None
    tags: list[str] = Field(default_factory=list)
```

### 3.2 修改 CLI payload（cli/market.py）

```python
# aln/cli/market.py publish_command

card = resolve_entity_card(entity_spec)
client = resolve_arbiter_client(card)
payload = {
    "order_type": order_type,
    "publisher": card.entity_uid,
    "publisher_address": card.address.address,  # 新增：完整地址
    "title": title,
    "description": description,
    "budget": budget,
    "tags": [t.strip() for t in tags.split(",")] if tags else [],
}
```

### 3.3 修改 publish_order API handler（api/v1/trade.py）

```python
# aln/app/api/v1/trade.py publish_order

async def publish_order(...) -> StandardResponse[dict]:
    _get_arbiter_checkpoint(current_host)
    # 不再调用 resolve_sender_entity（它只查本机）
    # CLI 侧已通过 resolve_entity_card 验证了 entity 存在
    address = request_data.publisher_address  # 直接使用 CLI 传来的完整地址
    order = store.publish(request_data, publisher_address=address)
    return StandardResponse[dict](
        success=True,
        message=f"Order published: {order.order_id}",
        data=order.model_dump(mode="json"),
    )
```

### 3.4 删除 / 下架的同步修改

`archive_order` 和 `delete_order` 中同样使用了 `resolve_sender_entity` 做权限校验
（确认请求者是订单发布者）。这些需要改为按 `publisher_address` 比对，
而不是在本机查找 entity：

```python
# archive / delete 中的权限校验改为：
if order.publisher_address != request_data.requester_address:
    raise HTTPException(403, "Only the publisher can archive/delete this order")
```


## 4. 修改后的调用链

```
CLI                              API (Arbiter Host)
────                             ─────────────────
1. resolve_entity_card(spec)     
   → 在 entity 所在 host 查到 ✓  
                                 
2. resolve_arbiter_client(card)  
   → 找到 Arbiter Host ✓         
                                 
3. payload = {                   
     "publisher": entity_uid,    
     "publisher_address": "host_uid:entity_uid"  ← 完整地址
   }                             
   client.market_publish(payload)
                                 4. 不再查本机 entity
                                    直接用 publisher_address 存储 ✓
```


## 5. 修改后 demo/quickstart.sh 可还原

修改完成后，quickstart.sh 中的 supply 订单可以恢复为各 Agent 自己发布：

```bash
# 还原为各 entity 自主发布
aln market publish -e "$CODER_ADDR" --type supply --title "全栈编程服务" ...
aln market publish -e "$RESEARCHER_ADDR" --type supply --title "深度研究与分析服务" ...
aln market publish -e "$REVIEWER_ADDR" --type supply --title "代码审查与质量分析" ...
```


## 6. 安全考量

当前方案信任 CLI 侧已验证 entity 存在（`resolve_entity_card` 会向源 Host 确认）。
如果未来需要 API 侧也做验证（防止伪造地址），可在 Arbiter Host 上增加：

1. 解析 `publisher_address` 中的 `host_uid`
2. 通过 parent/child 拓扑找到该 Host 的 URL
3. 向该 Host 发 HTTP 请求确认 entity 存在

这属于增强安全，v0.1 阶段可不做。
