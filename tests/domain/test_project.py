from pathlib import Path
import tempfile
import unittest

from src.csharp.project import check_project


class ProjectIntegrationTests(unittest.TestCase):
    def test_unexecuted_target_items_do_not_prove_project_membership(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, project = root/'Screen.cs', root/'Screen.csproj'
            source.write_text('class Screen {}', encoding='utf-8')
            project.write_text('<Project><Target Name="NeverRun"><ItemGroup><Compile Include="Screen.cs"/>'
                               '<Reference Include="Charts.UI"/></ItemGroup></Target></Project>', encoding='utf-8')
            result = check_project(project, [source], ['Charts.UI'])
            self.assertEqual('incomplete', result.status)
            self.assertEqual('unverified', result.metadata['project_integration']['files'][0]['status'])
            self.assertEqual('unverified', result.metadata['project_integration']['required_references'][0]['status'])

    def test_import_can_remove_explicit_membership_and_reference(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, project = root/'Screen.cs', root/'Screen.csproj'
            source.write_text('class Screen {}', encoding='utf-8')
            (root/'remove.targets').write_text('<Project><ItemGroup><Compile Remove="Screen.cs"/>'
                '<Reference Remove="Charts.UI"/></ItemGroup></Project>', encoding='utf-8')
            project.write_text('<Project><ItemGroup><Compile Include="Screen.cs"/><Reference Include="Charts.UI"/>'
                               '</ItemGroup><Import Project="remove.targets"/></Project>', encoding='utf-8')
            result = check_project(project, [source], ['Charts.UI'])
            self.assertEqual('incomplete', result.status)
            self.assertEqual('unverified', result.metadata['project_integration']['files'][0]['status'])
            self.assertEqual('unverified', result.metadata['project_integration']['required_references'][0]['status'])

    def test_registered_code_designer_resource_and_required_assembly_are_read_only(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            files = [root/name for name in ('Report.cs', 'Report.Designer.cs', 'Report.resx')]
            for path in files:
                path.write_text('source', encoding='utf-8')
            (root/'lib').mkdir()
            (root/'lib/Charts.UI.dll').write_bytes(b'dll')
            project = root/'Report.csproj'
            project.write_text('''<Project xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
              <ItemGroup><Compile Include="Report.cs"/><Compile Include="Report.Designer.cs"/>
              <EmbeddedResource Include="Report.resx"/><Reference Include="Charts.UI, Version=1.0.0.0">
              <HintPath>lib\\Charts.UI.dll</HintPath></Reference></ItemGroup>
            </Project>''', encoding='utf-8')
            before = {path: path.read_bytes() for path in root.rglob('*') if path.is_file()}
            result = check_project(project, files, ['charts.ui'])
            self.assertEqual('passed', result.status)
            self.assertEqual('verified_static', result.metadata['project_integration']['status'])
            self.assertEqual(3, len(result.metadata['project_integration']['files']))
            self.assertEqual(before, {path: path.read_bytes() for path in root.rglob('*') if path.is_file()})

    def test_same_basename_in_another_tree_does_not_establish_registration(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'actual').mkdir()
            (root/'staging').mkdir()
            for name in ('actual', 'staging'):
                (root/name/'Screen.cs').write_text('class Screen {}', encoding='utf-8')
            project = root/'Screen.csproj'
            project.write_text('<Project><ItemGroup><Compile Include="actual/Screen.cs"/></ItemGroup></Project>', encoding='utf-8')
            result = check_project(project, [root/'staging/Screen.cs'], ['Charts.UI'])
            self.assertEqual({'project_item_not_registered', 'project_required_reference_missing'},
                             {issue.code for issue in result.issues})

    def test_missing_literal_hint_and_selected_file_are_not_success(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            project = root/'Screen.csproj'
            project.write_text('<Project><ItemGroup><Reference Include="Charts.UI"><HintPath>missing.dll</HintPath>'
                               '</Reference></ItemGroup></Project>', encoding='utf-8')
            result = check_project(project, [root/'missing.cs'], ['Charts.UI'])
            self.assertEqual({'project_item_file_missing', 'project_reference_hint_missing'},
                             {issue.code for issue in result.issues})

    def test_generated_conditional_and_sdk_membership_remain_unverified(self):
        variants = [
            '<Project Sdk="Microsoft.NET.Sdk"/>',
            '<Project><ItemGroup Condition="\'$(Target)\' == \'x\'"><Compile Include="Screen.cs"/></ItemGroup></Project>',
            '<Project><ItemGroup><Compile Include="**/*.cs"/></ItemGroup></Project>',
            '<Project><ItemGroup><Compile Include="$(Source)/Screen.cs"/></ItemGroup></Project>',
            '<Project><Import Project="custom.targets"/></Project>',
            '<Project><ItemGroup><Compile Include="Screen.cs"/><Compile Remove="Screen.cs"/></ItemGroup></Project>',
        ]
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, project = root/'Screen.cs', root/'Screen.csproj'
            source.write_text('class Screen {}', encoding='utf-8')
            for xml in variants:
                with self.subTest(xml=xml):
                    project.write_text(xml, encoding='utf-8')
                    result = check_project(project, [source])
                    self.assertEqual('incomplete', result.status)
                    self.assertEqual('unverified', result.metadata['project_integration']['files'][0]['status'])
                    self.assertFalse(result.issues)

    def test_missing_hint_requires_resolver_review_instead_of_guessing_build_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder)/'Screen.csproj'
            project.write_text('<Project><ItemGroup><Reference Include="Charts.UI"><HintPath>missing.dll</HintPath>'
                               '</Reference></ItemGroup></Project>', encoding='utf-8')
            result = check_project(project, [], ['Charts.UI'])
            self.assertEqual('incomplete', result.status)
            self.assertEqual('warning', result.issues[0].severity)
            self.assertEqual('unverified', result.metadata['project_integration']['required_references'][0]['status'])

    def test_conditional_property_and_packaged_references_are_not_guessed_missing(self):
        variants = [
            '<Reference Include="Charts.UI" Condition="\'$(Target)\' == \'x\'"/>',
            '<Reference Include="Charts.UI"><HintPath>$(Lib)/Charts.UI.dll</HintPath></Reference>',
            '<Reference Include="$(ChartsAssembly)"/>',
            '<PackageReference Include="Charts" Version="1"/>',
        ]
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder)/'Screen.csproj'
            for xml in variants:
                with self.subTest(xml=xml):
                    project.write_text(f'<Project><ItemGroup>{xml}</ItemGroup></Project>', encoding='utf-8')
                    result = check_project(project, [], ['Charts.UI'])
                    self.assertEqual('incomplete', result.status)
                    self.assertFalse(result.issues)

    def test_bad_xml_is_an_input_error(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder)/'bad.csproj'
            project.write_text('<Project>', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Invalid project XML'):
                check_project(project, [])


if __name__ == '__main__':
    unittest.main()
