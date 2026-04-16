# Generalized Ordered Hierarchy Navigation Model

The interaction model is a focus-based navigation system for dense ordered structures. At rest, the full range remains visible in compressed form so the user retains awareness of the whole sequence. Nothing disappears. The interface preserves global position while sacrificing detail in regions that are not currently relevant.

As the pointer moves across the structure, local space is reallocated around the area of interest. The nearest entries expand, adjacent entries partially expand, and distant entries compress. This creates a continuous gradient between overview and detail rather than a hard switch between separate views. The result is that large ordered sets can occupy a fixed visual region without requiring uniformly precise targeting.

Pointer speed can also affect the amount of local expansion. Slow movement implies inspection, so the focus region can become narrower and more exact. Faster movement implies traversal, so the focus region can widen and become more forgiving. This lets the same structure support both scanning and precise selection without changing modes.

Selection introduces a second level of commitment. Hover indicates temporary attention. Selection indicates a decision to treat one entry as the active anchor. Once anchored, that selected entry can receive more space than a transient hover state, and a directly attached subordinate sequence can appear as a continuation of that entry rather than as a disconnected panel.

That subordinate sequence follows the same rules as the parent sequence. It remains compressed at rest, expands around attention, and can itself become the base for another attached sequence. In this way, the interaction model can recurse across any ordered hierarchy: time units, document outlines, category trees, indexes, address spaces, taxonomies, or layered symbolic systems.

The core idea is not “open a submenu.” It is “redistribute finite display space according to graded attention within an ordered hierarchy.” The user is always navigating both position and depth at once, with context preserved and detail emerging locally from the currently anchored path.
