"""Fixtures shared by every test module.

Nothing global here on purpose: only test_config_flow.py touches Home
Assistant's test harness, and it opts in itself via
`pytest.mark.usefixtures("enable_custom_integrations")`. test_api.py is a
plain asyncio/aiohttp-mock suite and must be able to run without the HA
harness installed at all.
"""
