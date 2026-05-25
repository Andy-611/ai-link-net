"""API endpoint constants for decoupling."""


class ENDPOINT:
    #TODO:列出所有 host server 的 API/WSS endpoint，保持与 host server 代码一致，并添加必要的注释说明。
    """API endpoint constants."""

    # Well-known
    WELL_KNOWN = "/.well-known"

    # Health
    HEALTH = "/health"

    # Children
    CHILDREN = "/api/v1/children"
    PARENT = "/api/v1/parent"

    # Entities
    ENTITIES = "/api/v1/entities"
    ENTITY_DISCOVER = "/api/v1/entities/discover"
    ENTITY_FRIENDS = "/api/v1/entities/{entity_uid}/friends"
    ENTITY_DETAIL = "/api/v1/entities/{entity_uid}"
    FRIEND_ADD = "/api/v1/friends/add"
    FRIEND_DELETE = "/api/v1/friends/delete"

    # Mail
    SEND_MAIL = "/api/v1/mail"

    # WebSocket (Host-to-Host communication)
    WS_HOST = "/ws"

    # UI control
    START_UI = "/api/v1/ui/start"
    STOP_UI = "/api/v1/ui/stop"

    # Trade
    TRADE_SEND = "/api/v1/trade/send"
    TRADE_CONTRACTS = "/api/v1/trade/contracts"
    TRADE_CONTRACT_DETAIL = "/api/v1/trade/contracts/{contract_id}"
    TRADE_PAYMENTS = "/api/v1/trade/payments"
    TRADE_BALANCE = "/api/v1/trade/balance/{entity_spec}"

    # Market (app-layer)
    MARKET_ORDERS = "/api/v1/trade/orders"
    MARKET_ORDER_DETAIL = "/api/v1/trade/orders/{order_id}"
    MARKET_ORDER_ARCHIVE = "/api/v1/trade/orders/{order_id}/archive"
