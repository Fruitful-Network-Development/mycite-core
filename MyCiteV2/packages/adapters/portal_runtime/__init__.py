"""Historical portal-runtime bridge package.

The package root intentionally exports no bridge symbols. Any remaining bridge
evidence must import `v1_host_bridge` directly so active code cannot treat this
package as a normal V2 adapter surface.
"""

__all__: list[str] = []
