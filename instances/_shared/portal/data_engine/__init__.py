from .anthology_normalization import CompactionResult, compact_iterations, datum_sort_key, parse_datum_identifier, sort_rows
from .anthology_context import AnthologyContext, build_canonical_anthology_context
from .anthology_overlay import (
    MergeReport,
    OverlayMigrationReport,
    load_overlay_merge_for_path,
    migrate_overlay_file,
    merge_base_and_overlay,
    strip_base_duplicates_from_overlay,
)
from .anthology_registry import BaseRegistry, default_base_registry_path, load_base_registry
from .anthology_schema import (
    NormalizedDatum,
    denormalize_compact_row,
    denormalize_row,
    detect_row_kind,
    normalize_compact_row,
    normalize_row,
    parse_id,
    sort_key,
    validate_row,
)
from .archetypes import ArchetypeDefinition, get_archetype_definition, list_archetype_definition_dicts, list_archetype_definitions
from .datum_identity import (
    CompiledDatumIndex,
    DatumResolution,
    build_compiled_index,
    compile_compact_array_entries_keyed_by_path,
    datum_paths_equivalent,
    parse_datum_path,
    resolve_to_contract_entry,
    resolve_to_local_row,
    stable_datum_id,
    to_canonical_dot,
)
from .field_contracts import FieldContract, default_profile_field_contracts
from .geometry_datums import GEOMETRY_TEMPLATES, geometry_template_spec
from .inherited_txa_adapter import (
    adapt_published_txa_resource_value,
    build_field_ref_bindings,
    select_inherited_binding_for_field,
    select_inherited_ref_for_field,
)
from .profile_config_refs import get_path, set_path
from .samras_descriptor_compiler import (
    compile_provisional_samras_descriptor,
    compile_samras_constraint_for_chain,
    compile_samras_descriptors_from_rows,
)
from .write_pipeline import WriteApplyResult, WritePreviewResult, apply_write_preview, preview_write_intent
from .rules import (
    ORDINAL_SEMANTICS_V1,
    value_group_as_int,
    DatumRow,
    DatumUnderstanding,
    DatumUnderstandingReport,
    RuleContext,
    RuleDefinition,
    ordered_pairs_from_row,
    reference_filter_options,
    resolve_lens_for_datum,
    understand_datums,
    validate_rule_create,
)


def inspect_archetype_context(*args, **kwargs):
    from mycite_core.state_machine.aitas import inspect_archetype_context as _inspect_archetype_context

    return _inspect_archetype_context(*args, **kwargs)


def inspect_archetype_trace(*args, **kwargs):
    from mycite_core.state_machine.aitas import inspect_archetype_trace as _inspect_archetype_trace

    return _inspect_archetype_trace(*args, **kwargs)


def list_derived_archetype_bindings(*args, **kwargs):
    from mycite_core.state_machine.aitas import list_derived_archetype_bindings as _list_derived_archetype_bindings

    return _list_derived_archetype_bindings(*args, **kwargs)


def list_archetype_registry_payload(*args, **kwargs):
    from mycite_core.state_machine.aitas import list_archetype_registry_payload as _list_archetype_registry_payload

    return _list_archetype_registry_payload(*args, **kwargs)


def get_archetype_definition_payload(*args, **kwargs):
    from mycite_core.state_machine.aitas import get_archetype_definition_payload as _get_archetype_definition_payload

    return _get_archetype_definition_payload(*args, **kwargs)

__all__ = [
    "CompiledDatumIndex",
    "CompactionResult",
    "AnthologyContext",
    "BaseRegistry",
    "MergeReport",
    "OverlayMigrationReport",
    "NormalizedDatum",
    "ArchetypeDefinition",
    "get_archetype_definition",
    "get_archetype_definition_payload",
    "build_compiled_index",
    "compile_compact_array_entries_keyed_by_path",
    "compact_iterations",
    "build_canonical_anthology_context",
    "default_base_registry_path",
    "denormalize_compact_row",
    "denormalize_row",
    "datum_sort_key",
    "detect_row_kind",
    "datum_paths_equivalent",
    "DatumResolution",
    "parse_datum_identifier",
    "parse_id",
    "parse_datum_path",
    "resolve_to_contract_entry",
    "resolve_to_local_row",
    "sort_rows",
    "sort_key",
    "normalize_compact_row",
    "normalize_row",
    "validate_row",
    "load_base_registry",
    "merge_base_and_overlay",
    "load_overlay_merge_for_path",
    "migrate_overlay_file",
    "strip_base_duplicates_from_overlay",
    "stable_datum_id",
    "to_canonical_dot",
    "FieldContract",
    "inspect_archetype_context",
    "inspect_archetype_trace",
    "list_archetype_definition_dicts",
    "list_archetype_definitions",
    "list_archetype_registry_payload",
    "list_derived_archetype_bindings",
    "default_profile_field_contracts",
    "GEOMETRY_TEMPLATES",
    "geometry_template_spec",
    "adapt_published_txa_resource_value",
    "build_field_ref_bindings",
    "select_inherited_binding_for_field",
    "select_inherited_ref_for_field",
    "get_path",
    "set_path",
    "compile_provisional_samras_descriptor",
    "compile_samras_descriptors_from_rows",
    "compile_samras_constraint_for_chain",
    "WriteApplyResult",
    "WritePreviewResult",
    "apply_write_preview",
    "preview_write_intent",
    "ORDINAL_SEMANTICS_V1",
    "value_group_as_int",
    "DatumRow",
    "DatumUnderstanding",
    "DatumUnderstandingReport",
    "RuleContext",
    "RuleDefinition",
    "ordered_pairs_from_row",
    "understand_datums",
    "reference_filter_options",
    "validate_rule_create",
    "resolve_lens_for_datum",
]
