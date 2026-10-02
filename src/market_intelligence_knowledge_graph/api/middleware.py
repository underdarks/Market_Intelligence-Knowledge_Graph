from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send


class RequestIdMiddleware:
    """요청마다 request_id 발급 -> request.state.request_id + 응답 헤더 X-Request-ID.
    클라이언트가 X-Request-ID를 보내면 그 값을 그대로 씀 (상위 시스템과 추적 연결)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":  # lifespan, websocket 등은 그대로 통과
            await self.app(scope, receive, send)
            return

        headers = dict(scope["headers"])  # ASGI 헤더는 (bytes, bytes) 목록, 이름은 소문자
        request_id = headers.get(b"x-request-id", b"").decode() or uuid4().hex
        # request.state는 scope["state"] dict를 감싼 것: 여기 넣으면 핸들러에서 request.state.request_id
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":  # 응답 헤더가 나가는 순간에 추가
                message["headers"] = [*message.get("headers", []), (b"x-request-id", request_id.encode())]
            await send(message)

        await self.app(scope, receive, send_with_request_id)
