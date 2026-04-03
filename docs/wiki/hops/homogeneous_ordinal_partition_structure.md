# Homogeneous Ordinal Partition Structure (HOPS)

## Purpose

A **Homogeneous Ordinal Partition Structure (HOPS)** is a structural magnitude used to define an ordered address schema for a continuum that is subdivided by level in a uniform way.

HOPS is intended for spaces such as:

- chronology
- coordinates
- angle or direction
- any other ordered partition whose parallel nodes at the same level share the same child capacity

A HOPS does **not** describe the occupied entries of a system. It describes the valid ordinal partition structure that later addresses may occupy.

Its job is therefore structural rather than documentary:

- it defines the available address levels
- it defines the denotational capacity at each level
- it allows addresses to be interpreted at different specificities within one schema
- it allows those addresses to be handled algorithmically without changing the underlying structure

This makes HOPS suitable for structures that are expected to remain stable once adopted.

---

## Core Contrast with SAMRAS

A HOPS is intentionally simpler than a **Shape-Addressed Mixed-Radix Address Space (SAMRAS)**.

### SAMRAS

SAMRAS exists for structures whose local branching may vary by parent. Its structural value therefore has to preserve reconstructible shape. The engine decodes a SAMRAS structure by reading a breadth-first sequence of child counts, from which valid addresses are then derived.

In that model:

- the structure carries variable local branching information
- the shape must be reconstructed from the structural value
- addresses are derived from that reconstructed topology

### HOPS

HOPS does not preserve variable local shape.

Instead, it preserves a fixed **ordered partition schema**. The structure only needs to say how many possible denotations exist at each level. Because every parallel node at a given level is assumed to have the same child capacity, there is no need to encode per-parent branching state.

In that model:

- the structure carries level capacities, not local child counts
- the structure defines a valid ordinal partition schema
- addresses are interpreted inside that schema

The practical contrast is:

> **SAMRAS reconstructs variable shape.**
>
> **HOPS defines fixed subdivision.**

---

## Algorithmic Identity and Contextual Difference

The structural algorithm used by HOPS is the same regardless of whether the structure is being used for time, coordinates, or another ordered continuum.

The difference between one HOPS and another is **not** the codec. The difference is the **interpretation layer** applied to the decoded denotation capacities.

So two HOPS structures may be algorithmically identical in handling while remaining functionally distinct in meaning:

- a chronological HOPS is interpreted over time-oriented units
- a spatial HOPS is interpreted over geographic or angular units
- another HOPS could be interpreted over any other ordered partitioned continuum

This distinction matters because the structure itself is abstract, while the domain semantics are contextual.

The structure answers:

- how many levels exist?
- how many denotations exist at each level?
- how is an address parsed or reconstructed?

The domain layer answers:

- what does each level mean?
- what interval or region does a selected address denote?
- how is that address projected into a human-facing context such as a time selection or geographic coordinate?

---

## Relation to the Anthology Abstraction Model

In the current anthology base, the two HOPS structures are not treated as isolated inventions. They are introduced through a layered abstraction chain that separates:

- ordinal position
- incremental unit
- structural magnitude
- operational space
- concrete named instance

The relevant abstractions are:

### Chronological axis

- `0-0-1` — `time-ordinal-position`
- `0-0-2` — `time-incramental-unit`
- `1-1-1` — `HOPS-chornological`
- `1-1-2` — `tiu-babel-second`
- `2-0-1` — `HOPS-space-chornological`
- `3-1-1` — `HOPS-babelette-UTC`

### Spatial axis

- `0-0-3` — `spacial-ordinal-position`
- `0-0-4` — `spacial-incramental-unit`
- `1-1-3` — `HOPS-spacial`
- `1-1-4` — `siu-babel-centameter`
- `2-0-2` — `HOPS-space-spacial`
- `3-1-2` — `HOPS-babelette-coordinate`

This separation is important.

The HOPS structural magnitude is not itself the unit and it is not itself the final named operational context. It is the structural authority that sits between ordinal abstraction and concrete contextual use.

That allows the same logic to be reused cleanly:

- the **ordinal-position** datum tells the system what kind of positional abstraction is being described
- the **incremental-unit** datum tells the system what smallest operational unit is associated with that space
- the **HOPS** datum defines the address schema for that space
- the **HOPS-space** datum treats that structure as an addressable domain
- the **babelette** datum gives a concrete named instance or handling context for that domain

This is the main abstraction pattern by which the chronological and spatial HOPS structures are derived in the anthology base.

---

## General HOPS Encoding Model

A HOPS uses the same broad unary-width and stop-slice discipline used in the SAMRAS prefixing logic, but it applies that logic to a sequence of fixed level capacities rather than a breadth-first child-count forest.

The encoded structure is formed as:

```text
[stop-index-width]
[denotation-count-width]
[denotation-count]
[stop-index-array]
[concatenated denotation binaries]
```

### Meaning of the fields

#### `stop-index-width`

A zero-run terminated by `1`.

The number of leading `0`s gives the bit-width used to store each stop index.

#### `denotation-count-width`

Another zero-run terminated by `1`.

The number of leading `0`s gives the bit-width used to store the number of denotations.

#### `denotation-count`

The number of denotational capacities carried by the structure.

#### `stop-index-array`

Cumulative exclusive stop positions used to slice the concatenated payload back into its component denotation binaries.

If there are `N` denotations, only `N - 1` stop indexes are needed because the final denotation runs to the end of the payload.

#### `concatenated denotation binaries`

The binary encodings of the denotational capacities, written as one continuous bit stream.

---

## Interpretation Rule

A HOPS structural magnitude defines the schema of an address space itself.

It does **not** describe a set of occupied nodes, scheduled events, or stored geographic objects.

It states only that:

- there is an ordered sequence of denotational capacities
- valid addresses are interpreted against that sequence
- reduced specificity may omit trailing levels without implying a different structure

So a shorter address inside a HOPS is not a new structure. It is a less specific position inside the same structure.

---

## Chronological HOPS

The chronological HOPS in the anthology base is the datum `1-1-1`, created in reference to `0-0-1` (`time-ordinal-position`). Its stored structural magnitude is:

```text
00000010001110000100001110011000100001100111111011111010001111101000101101101111100111100
```

The corresponding denotational capacities are interpreted as:

```text
14-1000-1000-365-60-60
```

This is a chronological partition structure.

Its interpretation is contextual rather than structural:

- the first denotations establish the large-scale chronological framing
- later denotations narrow toward year-, day-, and smaller-unit selection
- addresses inside the structure can therefore be used at different specificities while remaining structurally comparable

The paired incremental unit in the anthology base is `1-1-2` (`tiu-babel-second`). That unit does not replace the HOPS. It complements it by naming the smallest operating unit associated with the chronological space.

---

## Spatial HOPS

The spatial HOPS in the anthology base is the datum `1-1-3`, created in reference to `0-0-3` (`spacial-ordinal-position`). Its stored structural magnitude is:

```text
00000001000011001000100001011010010011001100000100111101110110101100010100011100100110010011001001100100110010011001001100100
```

The corresponding denotational capacities are interpreted as:

```text
8-81-100-100-100-100-100-100-100
```

This is a spatial partition structure.

The structure says:

- the first level has `8` denotations
- the second level has `81` denotations
- every later listed level has `100` denotations

The paired incremental unit in the anthology base is `1-1-4` (`siu-babel-centameter`). Again, that unit is not the structure itself. It is the named smallest operating unit associated with the spatial context built over that HOPS.

---

## Ordered Octet Naming for the Spatial HOPS

The first denotation of the spatial HOPS is an octet selector.

The ordered naming is:

```text
1 = NEG
2 = NEH
3 = NWH
4 = NWG
5 = SEG
6 = SEH
7 = SWH
8 = SWG
```

Expanded, this ordered naming uses:

- `N` / `S` for north and south
- `E` / `W` for east and west
- `H` / `G` for the added axis

The added axis describes the hemisphere division in which the prime meridian or antimeridian lies in the middle of the half, rather than serving as the boundary itself.

In this naming:

- `H` stands for **Heofon**, the near-ward hemisphere
- `G` stands for **Grundz**, the far-ward hemisphere

This gives the eight first-level spatial denotations a fixed ordinal naming system rather than treating them as anonymous octants.

---

## How a Spatial Address Is Understood

A spatial HOPS address is interpreted by repeated cell selection inside a fixed partition schema.

The algorithm remains the same at every level:

1. begin from the global domain implied by the first denotation
2. select the ordinal child cell for the current level
3. reduce the current cell to that selected child region
4. repeat until the address is exhausted

What changes by level is only the child capacity.

For the current spatial HOPS:

- level 1 selects one of 8 named globe octets
- level 2 selects one of 81 child cells, interpreted as a `9 × 9` partition inside that octet
- each later `100` level selects one of 100 child cells, interpreted as a `10 × 10` partition inside the current cell

This yields a fixed refinement process:

- `8` defines the initial globe partition
- `81` performs the first internal chunking of that root region
- later `100` values repeat decimal spatial refinement

The structure therefore remains algorithmically uniform even though the spatial meaning is geographic.

---

## Deriving a HOPS Spatial Address from a Coordinate

A geographic coordinate is not inserted into the structure directly. It is translated into an address by recursive ordinal partition selection.

The reasoning is:

1. determine which first-level octet contains the coordinate
2. place the coordinate inside that octet's local frame
3. compute which of the `81` second-level cells contains it
4. project the coordinate into that selected child cell's local frame
5. compute which of the next `100` cells contains it
6. repeat until the desired precision depth is reached

At each step, the coordinate is not being renamed arbitrarily. It is being converted into the ordinal index of the cell that contains it within the currently active parent region.

This is why a coordinate address is an **ordinal containment path** rather than a decimal string.

One current working example of this interpretation is:

```text
41.4993° N, 81.60° W
~ [-81.694472, 41.499353]
~ 3-76-10-64-99-49-43-75-23
```

The key reasoning is recursive containment by ordinal partition, not direct decimal transcription.

---

## Deriving Geographic Meaning from a Spatial Address

A spatial HOPS address should be understood as denoting a **cell**, not merely a dimensionless point.

From that cell, two common geographic projections can be derived:

- a bounding region
- a representative point

### Bounding region

The address may be resolved to the west, south, east, and north bounds of the final selected cell.

That resolved region can be emitted as a GeoJSON polygon.

### Representative point

The address may also be resolved to the centroid of the final selected cell.

That representative point can be emitted as a GeoJSON point.

In both cases, the HOPS address remains the structural identifier. The GeoJSON output is a projection derived from the selected region.

### Coordinate order

When projected into GeoJSON, coordinates are emitted in the standard order:

```text
[longitude, latitude]
```

not `[latitude, longitude]`.

---

## Functional Separation: Structure, Address, Projection

The handling of HOPS should remain separated into three layers.

### 1. Structure

The HOPS magnitude defines the legal partition schema.

### 2. Address

A HOPS address identifies an ordinal path inside that schema.

### 3. Projection

A domain-specific interpretation projects that address into a human-facing form such as:

- a selected day, month, or year
- a geographic coordinate region
- a GeoJSON point or polygon

This separation matters because the same HOPS algorithm can be reused across domains while preserving different contextual meanings.

---

## Why HOPS Exists Beside SAMRAS

HOPS is not a replacement for SAMRAS.

The two structures solve different problems.

### Use SAMRAS when:

- parent nodes may have different child counts
- the structure must preserve local branching shape
- valid addresses must be derived from a reconstructed topology
- the engine must rebuild that topology after mutation

### Use HOPS when:

- each level has a fixed child capacity across parallel nodes
- the structure defines a stable partition schema
- addresses represent ordinal position inside that schema
- the main task is interpretation, not shape reconstruction

So SAMRAS remains the correct structural class for variable topological address spaces, while HOPS is the correct structural class for fixed level-homogeneous ordinal partition spaces.

---

## Engine Ownership

As with SAMRAS, the HOPS codec and structural interpretation should remain engine-owned.

The human-facing system should work primarily with:

- HOPS structures as governing authorities
- addresses inside those structures
- domain projections derived from those addresses

The UI should not be responsible for raw bitstream editing.

The correct mutation or interpretation posture is:

- select or author an address inside a known HOPS
- let the engine validate that address against the governing structure
- let the engine derive the projected chronological or spatial meaning

That keeps the abstract structure stable and the contextual projection deterministic.

---

## Definition

> A **Homogeneous Ordinal Partition Structure (HOPS)** is a fixed, level-homogeneous structural magnitude that defines an ordered address schema for subdividing a continuum. Unlike SAMRAS, it does not encode per-parent branching shape. It encodes only the ordered denotational capacities required to partition a chronological, spatial, or otherwise ordered domain into nested ordinal positions.

---

## Short Contrast Statement

> **SAMRAS reconstructs shape.**
>
> **HOPS defines subdivision.**
