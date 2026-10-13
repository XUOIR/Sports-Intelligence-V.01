import asyncio
import json
import random
import httpx
from .config import settings
from .limits import limits

class ProviderError(RuntimeError):
    pass

class SafeHTTP:
    def __init__(self, guard=limits, transport=None):
        self.guard, self.transport = guard, transport

    async def request(self, provider: str, method: str, url: str, *, cost=1, cycle_id=None, **kwargs):
        if await self.guard.blocked(provider):
            raise ProviderError(f"{provider} circuit open")
        # Entire request/retry cycle deadline, including body streaming and sleep.
        try:
            async with asyncio.timeout(15 if provider == "openrouter" else 45):
                async with httpx.AsyncClient(timeout=15, follow_redirects=False, transport=self.transport) as client:
                    for attempt in range(3):
                        await self.guard.reserve(provider, cost)
                        if cycle_id:
                            await self.guard.llm_attempt(cycle_id)
                        async with client.stream(method, url, **kwargs) as response:
                            status = response.status_code
                            if status == 429:
                                if attempt == 2:
                                    await self.guard.trip(provider, 900)
                                    raise ProviderError("Rate-limit retry cap reached")
                                try:
                                    requested = max(0.0, float(response.headers.get("retry-after", 2 ** attempt)))
                                    if requested > 4:
                                        await self.guard.trip(provider, min(86400,max(900,int(requested))))
                                        raise ProviderError("Provider requested cooldown; request halted")
                                    delay = requested
                                except ValueError:
                                    delay = 2 ** attempt
                                await asyncio.sleep(delay + random.uniform(0, .25))
                                continue
                            if status >= 500:
                                await self.guard.trip(provider)
                                raise ProviderError(f"{provider} upstream outage ({status})")
                            if status >= 400:
                                if status in (401, 403):
                                    await self.guard.trip(provider, 86400)
                                raise ProviderError(f"{provider} rejected request ({status})")
                            if 300 <= status < 400:
                                # NHL's public /now endpoints redirect to dated/season URLs.
                                # Keep every hop on the official HTTPS API and within
                                # the existing three-request deadline and budget caps.
                                location = response.headers.get("location")
                                if provider == "nhl" and method.upper() == "GET" and location:
                                    destination = response.url.join(location)
                                    if (destination.scheme == "https" and destination.host == "api-web.nhle.com"
                                            and destination.port in (None, 443) and not destination.userinfo
                                            and destination.path.startswith("/v1/")):
                                        url = str(destination)
                                        continue
                                raise ProviderError("Upstream redirect rejected")
                            if provider == "odds" and response.headers.get("x-requests-remaining") == "0":
                                await self.guard.trip(provider, 86400)
                            content = bytearray()
                            async for chunk in response.aiter_bytes(chunk_size=65_536):
                                if len(content)+len(chunk) > settings.max_response_bytes:
                                    raise ProviderError("Upstream payload size limit exceeded")
                                content.extend(chunk)
                            try:
                                return json.loads(content)
                            except (ValueError, UnicodeError):
                                raise ProviderError("Upstream returned malformed JSON") from None
        except (TimeoutError, httpx.HTTPError):
            await self.guard.trip(provider)
            # No POST retry after timeout: the upstream may already have billed it.
            raise ProviderError(f"{provider} timeout/network failure") from None
        raise ProviderError("Request attempts exhausted")

http = SafeHTTP()
