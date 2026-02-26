"""RPC client for service-to-service communication"""

import asyncio
from typing import Any, Optional, Dict
import httpx
import structlog

from velvetecho.api.exceptions import VelvetEchoException

logger = structlog.get_logger(__name__)


class RPCException(VelvetEchoException):
    """Exception raised when RPC call fails"""

    def __init__(self, service: str, method: str, error: str, status_code: int = 500):
        super().__init__(
            message=f"RPC call failed: {service}.{method} - {error}",
            error_code="RPC_ERROR",
            status_code=status_code,
            details={"service": service, "method": method, "error": error},
        )


class RPCClient:
    """
    RPC client for service-to-service communication.

    Features:
    - HTTP-based RPC (JSON-RPC style)
    - Service discovery (static URLs)
    - Automatic retries
    - Timeout handling
    - Circuit breaker integration (optional)

    Example:
        rpc = RPCClient(services={
            "patientcomet": "http://localhost:9800",
            "whalefin": "http://localhost:8002",
        })

        # Call remote method
        result = await rpc.call(
            service="patientcomet",
            method="run_analysis",
            params={"workspace_id": "123"}
        )
    """

    def __init__(
        self,
        services: Dict[str, str],  # service_name -> base_url
        timeout: int = 30,
        max_retries: int = 3,
    ):
        self.services = services
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None

    async def connect(self) -> None:
        """Initialize HTTP client"""
        if self._client is not None:
            return

        self._client = httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
        )

        logger.info("RPC client initialized", services=list(self.services.keys()))

    async def disconnect(self) -> None:
        """Close HTTP client"""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.info("RPC client disconnected")

    async def call(
        self,
        service: str,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> Any:
        """
        Call a remote method on a service.

        Args:
            service: Service name (must be registered)
            method: Method name (e.g., "run_analysis")
            params: Method parameters
            timeout: Optional timeout override

        Returns:
            Method result

        Raises:
            RPCException: If call fails
        """
        if self._client is None:
            await self.connect()

        if service not in self.services:
            raise RPCException(service, method, f"Service not registered: {service}", 404)

        base_url = self.services[service]
        url = f"{base_url}/rpc/{method}"

        logger.info("RPC call started", service=service, method=method, url=url)

        # Retry loop
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = await self._client.post(
                    url,
                    json=params or {},
                    timeout=timeout or self.timeout,
                )

                if response.status_code == 200:
                    result = response.json()

                    logger.info(
                        "RPC call succeeded",
                        service=service,
                        method=method,
                        attempt=attempt + 1,
                    )

                    return result.get("data")
                else:
                    error_data = response.json()
                    error_msg = error_data.get("message", "Unknown error")

                    logger.error(
                        "RPC call failed",
                        service=service,
                        method=method,
                        status=response.status_code,
                        error=error_msg,
                        attempt=attempt + 1,
                    )

                    last_error = RPCException(service, method, error_msg, response.status_code)

            except httpx.TimeoutException as e:
                logger.warning(
                    "RPC call timed out",
                    service=service,
                    method=method,
                    attempt=attempt + 1,
                )
                last_error = RPCException(service, method, f"Timeout after {timeout}s", 504)

            except httpx.ConnectError as e:
                logger.warning(
                    "RPC call connection failed",
                    service=service,
                    method=method,
                    attempt=attempt + 1,
                    error=str(e),
                )
                last_error = RPCException(service, method, "Connection failed", 503)

            except Exception as e:
                logger.error(
                    "RPC call unexpected error",
                    service=service,
                    method=method,
                    attempt=attempt + 1,
                    error=str(e),
                    exc_info=True,
                )
                last_error = RPCException(service, method, str(e), 500)

            # Exponential backoff
            if attempt < self.max_retries - 1:
                backoff = 2**attempt
                await asyncio.sleep(backoff)

        # All retries failed
        raise last_error

    async def call_batch(
        self,
        calls: list[Dict[str, Any]],  # [{"service": "...", "method": "...", "params": {...}}, ...]
    ) -> list[Any]:
        """
        Call multiple RPC methods in parallel.

        Args:
            calls: List of call specs

        Returns:
            List of results (in same order as calls)

        Example:
            results = await rpc.call_batch([
                {"service": "patientcomet", "method": "get_workspace", "params": {"id": "1"}},
                {"service": "whalefin", "method": "list_agents", "params": {}},
            ])
        """
        tasks = [
            self.call(
                service=call["service"],
                method=call["method"],
                params=call.get("params"),
            )
            for call in calls
        ]

        return await asyncio.gather(*tasks, return_exceptions=True)

    def register_service(self, name: str, base_url: str) -> None:
        """Register a new service"""
        self.services[name] = base_url
        logger.info("Registered RPC service", service=name, base_url=base_url)

    def unregister_service(self, name: str) -> None:
        """Unregister a service"""
        if name in self.services:
            del self.services[name]
            logger.info("Unregistered RPC service", service=name)


# Convenience function for single global client
_global_rpc: Optional[RPCClient] = None


def get_rpc_client() -> RPCClient:
    """Get global RPC client instance"""
    global _global_rpc
    if _global_rpc is None:
        raise RuntimeError("RPC client not initialized. Call init_rpc_client() first.")
    return _global_rpc


def init_rpc_client(services: Dict[str, str], timeout: int = 30) -> RPCClient:
    """Initialize global RPC client"""
    global _global_rpc
    _global_rpc = RPCClient(services=services, timeout=timeout)
    return _global_rpc
