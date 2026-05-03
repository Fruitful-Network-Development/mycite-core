from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

ADAPTER_SOURCE = (
    REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "static" / "v2_portal_tool_surface_adapter.js"
).read_text(encoding="utf-8")

WORKBENCH_SOURCE = (
    REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "static" / "v2_portal_workbench_renderers.js"
).read_text(encoding="utf-8")

INSPECTOR_SOURCE = (
    REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "static" / "v2_portal_inspector_renderers.js"
).read_text(encoding="utf-8")

AWS_SOURCE = (
    REPO_ROOT / "MyCiteV2" / "instances" / "_shared" / "portal_host" / "static" / "v2_portal_aws_workspace.js"
).read_text(encoding="utf-8")


class RendererBranchCoverageTests(unittest.TestCase):
    """Verify that every canonical tool slug resolves to a registered renderer
    branch (or is explicitly documented as deferred) via the adapter module
    spec maps. Prevents silent fallback to generic renderers."""

    def test_cts_gis_presentation_surface_is_registered(self) -> None:
        self.assertIn('"system.tools.cts_gis"', ADAPTER_SOURCE,
                      "CTS-GIS must be registered in resolvePresentationSurfaceModuleSpec")

    def test_aws_csm_presentation_surface_is_registered(self) -> None:
        self.assertIn('"system.tools.aws_csm"', ADAPTER_SOURCE,
                      "AWS-CSM must be registered in resolvePresentationSurfaceModuleSpec")

    def test_aws_csm_reflective_workspace_is_registered(self) -> None:
        self.assertIn('"system.tools.aws_csm"', ADAPTER_SOURCE,
                      "AWS-CSM must be registered in resolveReflectiveWorkspaceModuleSpec")

    def test_fnd_ebi_is_not_registered_as_active_surface(self) -> None:
        # FND-EBI renderer is intentionally deferred.
        # It must NOT appear as a live registered entry in either spec map.
        # When a dedicated FND-EBI renderer is added, this test must be updated
        # together with the surface_catalog.md posture reclassification.
        self.assertNotIn('"system.tools.fnd_ebi": {', ADAPTER_SOURCE,
                         "FND-EBI must not be registered as an active renderer spec until a "
                         "dedicated renderer module exists and surface_catalog.md is updated")

    def test_adapter_exposes_canonical_aws_row_helpers(self) -> None:
        self.assertIn("buildAwsProfileRows", ADAPTER_SOURCE,
                      "Adapter must own canonical AWS profile row builder")
        self.assertIn("buildAwsNewsletterRows", ADAPTER_SOURCE,
                      "Adapter must own canonical AWS newsletter row builder")

    def test_aws_workspace_delegates_profile_rows_to_adapter(self) -> None:
        self.assertIn("toolSurfaceAdapter().buildAwsProfileRows", AWS_SOURCE,
                      "AWS workspace must delegate profile row derivation to PortalToolSurfaceAdapter")

    def test_aws_workspace_uses_shared_request_builder(self) -> None:
        self.assertIn("toolSurfaceAdapter().buildDirectSurfaceRequest", AWS_SOURCE,
                      "AWS workspace must use buildDirectSurfaceRequest from PortalToolSurfaceAdapter")

    def test_aws_users_tab_function_exists_and_contains_gallery_and_editor(self) -> None:
        self.assertIn("function renderInspectorUsersTab(workspace, surfacePayload)", AWS_SOURCE,
                      "renderInspectorUsersTab must be defined")
        start = AWS_SOURCE.index("function renderInspectorUsersTab(workspace, surfacePayload)")
        end = AWS_SOURCE.index("function renderInspectorOnboardingTab(workspace, surfacePayload)")
        users_tab_source = AWS_SOURCE[start:end]
        self.assertIn("renderMailboxGallery", users_tab_source,
                      "Users tab must render the mailbox gallery")
        self.assertIn("renderCreateProfileCard", users_tab_source,
                      "Users tab must render the create profile (Add User) form")
        self.assertIn("renderProfileEditorCard", users_tab_source,
                      "Users tab must render the profile editor when a profile is selected")

    def test_aws_newsletter_tab_function_exists_and_gates_dispatch_on_sender_confirmed(self) -> None:
        self.assertIn("function renderInspectorNewsletterTab(workspace, surfacePayload)", AWS_SOURCE,
                      "renderInspectorNewsletterTab must be defined")
        start = AWS_SOURCE.index("function renderInspectorNewsletterTab(workspace, surfacePayload)")
        end = AWS_SOURCE.index("function renderInspectorDomainTab(workspace, surfacePayload)")
        newsletter_tab_source = AWS_SOURCE[start:end]
        self.assertIn("selected_newsletter", newsletter_tab_source,
                      "Newsletter tab must check workspace.selected_newsletter")
        self.assertIn("senderConfirmed", newsletter_tab_source,
                      "Newsletter tab must compute senderConfirmed from mailbox_rows")
        self.assertIn("dispatch_newsletter", newsletter_tab_source,
                      "Newsletter tab must include dispatch_newsletter action button")
        self.assertIn("data-aws-assign-newsletter-sender-form", newsletter_tab_source,
                      "Newsletter tab must include sender assignment form")
        self.assertIn("subscribedCount", newsletter_tab_source,
                      "Newsletter tab must surface subscribedCount for the dispatch gate")
        # Dispatch button must be disabled when sender not confirmed
        self.assertIn('disabled="disabled"', newsletter_tab_source,
                      "Newsletter tab must disable dispatch button when gate conditions are not met")

    def test_aws_newsletter_tab_conditional_renders_absent_message_when_no_newsletter(self) -> None:
        start = AWS_SOURCE.index("function renderInspectorNewsletterTab(workspace, surfacePayload)")
        end = AWS_SOURCE.index("function renderInspectorDomainTab(workspace, surfacePayload)")
        newsletter_tab_source = AWS_SOURCE[start:end]
        self.assertIn("No newsletter profile is configured for this domain.", newsletter_tab_source,
                      "Newsletter tab must render an absent-state message when selected_newsletter is null")

    def test_aws_domain_infra_tab_contains_ses_and_receipt_fields_only(self) -> None:
        self.assertIn("function renderInspectorDomainInfraTab(workspace, surfacePayload)", AWS_SOURCE,
                      "renderInspectorDomainInfraTab must be defined")
        start = AWS_SOURCE.index("function renderInspectorDomainInfraTab(workspace, surfacePayload)")
        end = AWS_SOURCE.index("function renderInspectorNewsletterTab(workspace, surfacePayload)")
        domain_infra_source = AWS_SOURCE[start:end]
        self.assertIn('"ses_identity_status"', domain_infra_source,
                      "Domain infra tab must surface ses_identity_status")
        self.assertIn('"receipt_rule_status"', domain_infra_source,
                      "Domain infra tab must surface receipt_rule_status")
        self.assertNotIn("renderMailboxGallery", domain_infra_source,
                         "Domain infra tab must NOT include the mailbox gallery (belongs to Users tab)")
        self.assertNotIn("renderProfileEditorCard", domain_infra_source,
                         "Domain infra tab must NOT include the profile editor (belongs to Users tab)")

    def test_aws_inspector_tab_registration_uses_four_tab_structure(self) -> None:
        self.assertIn('{ id: "users", label: "Users", active: true }', AWS_SOURCE,
                      "Inspector must register a Users tab")
        self.assertIn('{ id: "newsletter", label: "Newsletter", active: hasNewsletter }', AWS_SOURCE,
                      "Inspector must register a conditional Newsletter tab")
        self.assertIn('activeInspectorTabId(tabs, "users")', AWS_SOURCE,
                      "Inspector must default to the users tab")
        self.assertIn('renderInspectorTabPanel("newsletter"', AWS_SOURCE,
                      "Inspector must render the newsletter tab panel")

    def test_aws_domain_tab_surfaces_selected_mailbox_onboarding_stage(self) -> None:
        start = AWS_SOURCE.index("function renderInspectorOnboardingTab(workspace, surfacePayload)")
        end = AWS_SOURCE.index("function renderInspectorDomainInfraTab(workspace, surfacePayload)")
        onboarding_tab_source = AWS_SOURCE[start:end]

        self.assertIn("renderOnboardingSection", onboarding_tab_source,
                      "AWS onboarding tab must call renderOnboardingSection")
        self.assertIn("renderDomainOnboardingCard", onboarding_tab_source,
                      "AWS onboarding tab must include domain onboarding card when no profile selected")


class CtsGisWorkbenchEvidenceSplitTests(unittest.TestCase):
    """Verify that the CTS-GIS workbench secondary evidence block and the inspector
    staging widget are intentionally separate surfaces (diagnostic vs. interactive),
    not accidental duplication."""

    def test_workbench_has_secondary_evidence_renderer(self) -> None:
        self.assertIn("renderSecondaryEvidenceSurface", WORKBENCH_SOURCE,
                      "Workbench must have a secondary evidence renderer for CTS-GIS diagnostic view")

    def test_workbench_cts_gis_block_reads_source_evidence(self) -> None:
        self.assertIn("source_evidence", WORKBENCH_SOURCE,
                      "Workbench CTS-GIS block must read from source_evidence (diagnostic path)")

    def test_inspector_has_interactive_staging_widget(self) -> None:
        self.assertIn("renderCtsGisStagingWidget", INSPECTOR_SOURCE,
                      "Inspector must own the interactive staging widget renderer")

    def test_staging_widget_not_duplicated_in_workbench(self) -> None:
        self.assertNotIn("renderCtsGisStagingWidget", WORKBENCH_SOURCE,
                         "renderCtsGisStagingWidget must not be duplicated in workbench renderer; "
                         "workbench shows read-only diagnostic view only")

    def test_workbench_cts_gis_block_does_not_read_interface_body(self) -> None:
        # The workbench diagnostic view must not reach into interface_body.staging_widget;
        # that payload is inspector-only.
        self.assertNotIn("interface_body.staging_widget", WORKBENCH_SOURCE,
                         "Workbench CTS-GIS block must not read from interface_body.staging_widget")
