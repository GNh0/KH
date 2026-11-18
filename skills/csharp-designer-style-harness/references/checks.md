# Optional C# static checks

Choose the command for the artifact you changed. Use the real pre-change source, the target control definitions and the approved same-role Designer when they apply.

```text
python <plugin-root>/scripts/kh_check.py csharp <screen.cs> --designer <screen.Designer.cs>
python <plugin-root>/scripts/kh_check.py designer <after.Designer.cs> --original <before.Designer.cs> --control-source <control.cs> --style-reference-designer <approved.Designer.cs>
python <plugin-root>/scripts/kh_check.py sp-call <selected-call.cs> <procedure.sql>
```

- **Font and alignment.** Compare fonts with established screen roles and effective alignment with the actual control initialization. Obtain a baseline or approved reference when a screen-specific font differs from the constructor.
- **Height.** Compare visible similar inputs and labels by layout role. Verify actual screen rendering and constraints for scaled controls.
- **Database calls.** Use one selected invocation for the parameter check. Trace mode values, XML shape, output bindings and result cardinality across both sources.
- **Completion.** Inspect the saved changes, correct confirmed violations and recheck affected behavior. For a checker finding or advanced option, open the relevant heading in the [checker reference](checker-details.md).
