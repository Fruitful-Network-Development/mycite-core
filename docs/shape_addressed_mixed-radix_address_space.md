# Shape-Addressed Mixed-Radix Address Space

## Purpose

This document defines the logical and algorithmic process for representing a **Shape-Addressed Mixed-Radix Address Space (SAMRAS)** as a structural value.

The purpose of this model is:

- to treat a SAMRAS datum as a **structural value**, not a free-form human-authored magnitude,
- to derive valid address spaces from a canonical structure,
- to allow address-based editing of nodes,
- to recompile the governing structural magnitude deterministically after edits,
- to make every SAMRAS structure either **valid** or **invalid** under explicit rules.

This document is written as a pseudo-code specification and implementation guide.

---

## Core idea

A SAMRAS structure defines a **tree or forest of nodes**.

Each node does **not** store its address explicitly inside the structure value.
Instead:

1. the structure stores a sequence of **child counts**,
2. the system interprets those child counts in **breadth-first order**,
3. addresses are then derived from **ordinal child position**.

So:

- the **structure value** defines the valid address space,
- the **address magnitudes** reference positions inside that defined space.

This means:

- addresses are **derived from structure**,
- but sandbox/resource editing should allow users to **edit the structure through addresses**,
- then the engine must **rebuild the structure value** automatically.

---

## Governing datum rule

A SAMRAS structure datum is a layer-1 datum created in reference to:

- `0-0-5` = nominal ordinal position

In this model, any datum created there is understood as a **SAMRAS structural value**.

---

## High-level model

A SAMRAS structural value is encoded as five parts:

1. `address_width_field`
2. `stop_count_width_field`
3. `stop_count_field`
4. `stop_address_array`
5. `value_stream`

The value stream encodes a sequence of variable-width binary values.
The stop-address array tells the decoder how to slice that stream into individual values.

---

## Canonical interpretation of the value sequence

Let the decoded values be:

- `v0, v1, v2, ..., vn`

Interpret them like this:

- `v0` = number of root nodes in the forest
- every later `vi` = number of children under the next node in breadth-first order

Then addresses are assigned by ordinal position:

- root nodes: `1`, `2`, ..., `v0`
- if node `a` has `k` children, then its children are:
  - `a-1`, `a-2`, ..., `a-k`

Example:

If the child-count sequence is:

- `3, 1, 2, 0, 0, 1, 0`

Then:

- `3` roots exist: `1`, `2`, `3`
- node `1` has 1 child: `1-1`
- node `2` has 2 children: `2-1`, `2-2`
- node `3` has 0 children
- node `1-1` has 0 children
- node `2-1` has 1 child: `2-1-1`
- node `2-2` has 0 children

---

## Address derivation rule

Addresses are not stored explicitly in the structure value.
They are derived from the breadth-first child-count interpretation.

Pseudo-code:

```text
function derive_addresses_from_child_counts(values):
    root_count = values[0]

    queue = []
    addresses = []
    next_value_index = 1

    for i from 1 to root_count:
        root_address = str(i)
        queue.push(root_address)
        addresses.append(root_address)

    while queue is not empty:
        parent = queue.pop_front()

        if next_value_index >= length(values):
            raise InvalidStructure("not enough child-count values")

        child_count = values[next_value_index]
        next_value_index += 1

        for child_ordinal from 1 to child_count:
            child_address = parent + "-" + str(child_ordinal)
            queue.push(child_address)
            addresses.append(child_address)

    if next_value_index != length(values):
        raise InvalidStructure("unused values remain after queue is exhausted")

    return addresses
```

---

## Structural encoding layout

### 1. Address width field

This field encodes how many bits are used to store each stop address.

Rule:

- a run of `0`s terminated by `1`
- the number of leading `0`s is the width

Example:

- `00001` means width = 4
- `00000000001` means width = 10

Pseudo-code:

```text
function encode_unary_width(width):
    return repeat("0", width) + "1"

function decode_unary_width(bitstream, start_index):
    count = 0
    i = start_index

    while i < length(bitstream) and bitstream[i] == "0":
        count += 1
        i += 1

    if i >= length(bitstream) or bitstream[i] != "1":
        raise InvalidStructure("unterminated unary width field")

    return (count, i + 1)
```

---

### 2. Stop-count width field

This field encodes how many bits are used to store the `stop_count`.

It uses the same unary-width rule.

---

### 3. Stop-count field

This field encodes how many stop addresses exist.

Important:

- if `stop_count = N`
- then there are `N + 1` decoded values in the value stream

Because the stop addresses denote slices:

- `[:s1]`
- `[s1:s2]`
- ...
- `[sN:]`

So the stop count is **not** the number of final values.
It is the number of stop boundaries.

Pseudo-code:

```text
function encode_fixed_width_binary(value, width):
    bits = binary(value)
    if length(bits) > width:
        raise InvalidStructure("value does not fit in fixed width")
    return left_pad(bits, width, "0")
```

---

### 4. Stop-address array

The stop-address array contains cumulative **exclusive** end positions into the value stream.

If the value stream is sliced by:

- `[:2]`
- `[2:4]`
- `[4:6]`

then the stop-address array is:

- `[2, 4, 6]`

Rules:

- strictly increasing
- each stop address must fit within `address_width_bits`
- the final stop address must be less than or equal to the length of the value stream
- if there are `N` stop addresses, they yield `N + 1` decoded values

Pseudo-code:

```text
function validate_stop_addresses(stops, value_stream_length):
    if length(stops) == 0:
        return

    prev = None
    for s in stops:
        if s < 0:
            raise InvalidStructure("negative stop address")
        if prev is not None and s <= prev:
            raise InvalidStructure("stop addresses must be strictly increasing")
        if s > value_stream_length:
            raise InvalidStructure("stop address exceeds value stream length")
        prev = s
```

---

### 5. Value stream

The value stream is a continuous bit string formed by concatenating variable-width binary values.

Example values:

- `1`
- `10`
- `10`
- `1`
- `100`
- `0`

become:

- `1101011000`

The stop-address array defines how to split it back into those tokens.

Pseudo-code:

```text
function slice_value_stream(value_stream, stops):
    values = []
    start = 0

    for stop in stops:
        values.append(value_stream[start:stop])
        start = stop

    values.append(value_stream[start:])

    return values
```

---

## Full decode algorithm

```text
function decode_samras(bitstream):
    cursor = 0

    (address_width_bits, cursor) = decode_unary_width(bitstream, cursor)
    (stop_count_width_bits, cursor) = decode_unary_width(bitstream, cursor)

    stop_count_bits = bitstream[cursor : cursor + stop_count_width_bits]
    if length(stop_count_bits) != stop_count_width_bits:
        raise InvalidStructure("truncated stop-count field")
    stop_count = binary_to_int(stop_count_bits)
    cursor += stop_count_width_bits

    stops = []
    for i from 1 to stop_count:
        stop_bits = bitstream[cursor : cursor + address_width_bits]
        if length(stop_bits) != address_width_bits:
            raise InvalidStructure("truncated stop-address array")
        stops.append(binary_to_int(stop_bits))
        cursor += address_width_bits

    value_stream = bitstream[cursor:]

    validate_stop_addresses(stops, length(value_stream))

    raw_value_tokens = slice_value_stream(value_stream, stops)

    if any(token == "" for token in raw_value_tokens):
        raise InvalidStructure("empty value token")

    values = []
    for token in raw_value_tokens:
        values.append(binary_to_int(token))

    addresses = derive_addresses_from_child_counts(values)

    return {
        "address_width_bits": address_width_bits,
        "stop_count_width_bits": stop_count_width_bits,
        "stop_count": stop_count,
        "stop_addresses": stops,
        "value_tokens": raw_value_tokens,
        "values": values,
        "addresses": addresses,
    }
```

---

## Full encode algorithm from an address set

This is the reverse process.

### Step 1: validate address set

The addresses must satisfy:

- each segment is a positive integer,
- root ordinals are contiguous from `1`,
- each node's child ordinals are contiguous from `1`,
- every non-root address has an existing parent.

Pseudo-code:

```text
function validate_address_set(addresses):
    normalized = sort_addresses(addresses)

    parent_to_children = {}
    roots = []

    for address in normalized:
        segments = parse_address(address)

        if length(segments) == 1:
            roots.append(segments[0])
        else:
            parent = join_segments(segments[:-1])
            child_ordinal = segments[-1]

            if parent not in normalized:
                raise InvalidStructure("missing parent for address " + address)

            parent_to_children[parent].append(child_ordinal)

    if roots != [1, 2, ..., length(roots)]:
        raise InvalidStructure("roots must be contiguous from 1")

    for parent, ordinals in parent_to_children.items():
        sorted_ordinals = sort(ordinals)
        expected = [1, 2, ..., length(sorted_ordinals)]
        if sorted_ordinals != expected:
            raise InvalidStructure("child ordinals must be contiguous for " + parent)
```

---

### Step 2: compute child counts in breadth-first order

```text
function child_counts_from_addresses(addresses):
    validate_address_set(addresses)

    parent_to_children = build_parent_child_map(addresses)
    root_count = count_roots(addresses)

    values = [root_count]
    queue = []

    for i from 1 to root_count:
        queue.push(str(i))

    while queue is not empty:
        node = queue.pop_front()
        children = sorted_children_of(node, parent_to_children)
        values.append(length(children))

        for child in children:
            queue.push(child)

    return values
```

---

### Step 3: encode value tokens as minimal binary

```text
function minimal_binary(value):
    if value == 0:
        return "0"
    return binary(value)
```

---

### Step 4: compute stop addresses

If the token binaries are:

- `t0, t1, ..., tn`

then stop addresses are cumulative exclusive endpoints for every token except the last.

```text
function compute_stop_addresses(value_tokens):
    stops = []
    total = 0

    for i from 0 to length(value_tokens) - 2:
        total += length(value_tokens[i])
        stops.append(total)

    return stops
```

---

### Step 5: compute widths and final bitstream

```text
function width_bits_for_integer(value):
    if value == 0:
        return 1
    return length(binary(value))

function encode_samras_from_addresses(addresses):
    values = child_counts_from_addresses(addresses)

    value_tokens = []
    for v in values:
        value_tokens.append(minimal_binary(v))

    stop_addresses = compute_stop_addresses(value_tokens)

    value_stream = concatenate(value_tokens)

    max_stop = max(stop_addresses) if length(stop_addresses) > 0 else 0
    address_width_bits = width_bits_for_integer(max_stop)

    stop_count = length(stop_addresses)
    stop_count_width_bits = width_bits_for_integer(stop_count)

    out = ""
    out += encode_unary_width(address_width_bits)
    out += encode_unary_width(stop_count_width_bits)
    out += encode_fixed_width_binary(stop_count, stop_count_width_bits)

    for stop in stop_addresses:
        out += encode_fixed_width_binary(stop, address_width_bits)

    out += value_stream

    return {
        "bitstream": out,
        "values": values,
        "value_tokens": value_tokens,
        "stop_addresses": stop_addresses,
        "address_width_bits": address_width_bits,
        "stop_count_width_bits": stop_count_width_bits,
        "stop_count": stop_count,
    }
```

---

## Canonical mutation rule

When a user adds or edits a SAMRAS node, the engine must not edit the raw magnitude directly.

The correct mutation process is:

1. decode current SAMRAS structure
2. reconstruct the canonical address tree
3. apply address-level mutation
4. revalidate address continuity
5. regenerate breadth-first child counts
6. regenerate stop-address table
7. regenerate final bitstream
8. write that new canonical structural magnitude

Pseudo-code:

```text
function add_child_to_address(existing_addresses, parent_address):
    if parent_address not in existing_addresses:
        raise InvalidStructure("parent address does not exist")

    child_ordinals = children_of(parent_address, existing_addresses)
    next_child_ordinal = length(child_ordinals) + 1

    new_address = parent_address + "-" + str(next_child_ordinal)

    updated = copy(existing_addresses)
    updated.add(new_address)

    validate_address_set(updated)

    return {
        "new_addresses": updated,
        "new_address": new_address,
        "new_samras": encode_samras_from_addresses(updated),
    }
```

---

## Example mutation

If:

- `1-1-3-3-5-6-7-2-1-1` exists
- and it currently has only one child:
  - `1-1-3-3-5-6-7-2-1-1-1`

then adding another cultivar gives:

- new child = `1-1-3-3-5-6-7-2-1-1-2`

The engine must then:

- increment that parent's child count,
- regenerate the breadth-first value stream,
- recompute stop addresses,
- rewrite the final SAMRAS magnitude.

The new address is valid only after the structural value is rebuilt.

---

## Formal validity conditions

A SAMRAS structure is valid if and only if all are true:

1. it is created in reference to `0-0-5`
2. width fields decode correctly
3. stop count decodes correctly
4. stop-address array length matches stop count
5. stop-address array is strictly increasing
6. stop-address array does not exceed value-stream length
7. value stream yields no empty slices
8. first decoded value is a valid root count
9. breadth-first child-count decode consumes all tokens exactly
10. every derived address is unique
11. every later SAMRAS-space reference points to an address that actually exists in the decoded structure

---

## Formal invalidity conditions

A SAMRAS structure is invalid if any of the following occur:

- width field is unterminated
- stop-count field is truncated
- stop-address array is truncated
- a stop address decreases or repeats
- a stop address exceeds the value stream
- a slice is empty
- the breadth-first queue underflows or overflows relative to the token count
- unused tokens remain after the queue empties
- a referenced address uses a child ordinal that exceeds what the structure allows
- roots or children are non-contiguous

---

## Practical implementation notes

### Engine ownership
These semantics should be owned by the data engine / shared core.

### UI role
The UI should edit:

- address tree
- node additions
- node removals
- node inspection

The UI should not be responsible for raw SAMRAS bit manipulation.

### Canonical write rule
Canonical save should write the structural bitstream only.
Legacy hyphenated human-authored SAMRAS magnitudes should be migration-only inputs.

---

## Recommended module split

Suggested shared-core modules:

- `samras_codec.py`
  - encode/decode bitstream
- `samras_structure.py`
  - internal structure model
- `samras_validation.py`
  - validity predicates
- `samras_mutation.py`
  - add/remove/rebuild operations
- `samras_workspace_adapter.py`
  - shape for sandbox/resource editor use

---

## Final summary

A SAMRAS structural datum should be understood as:

- a serialized breadth-first child-count forest,
- with variable-width binary values,
- parsed by a stop-address array,
- from which addresses are derived by ordinal child position.

The correct human-facing model is:

- **edit addresses / nodes**
- **engine regenerates structure**
- **engine rewrites canonical magnitude**

That is the logical basis required for flawless validation and mutation.
