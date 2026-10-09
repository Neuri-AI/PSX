# REF-M3 markup resolver and compiler decoupling

The markup compiler now resolves tags through `ComponentRegistry` definitions. The parser, lexer and AST are unchanged.

## Resolution order

1. A supplied `registry` resolves a tag from its immutable snapshot.
2. Without a registry, a fresh built-in registry supplies the legacy built-ins.
3. The legacy `primitives` mapping remains supported with its prior replacement-mapping behavior.
4. An unresolved tag can still resolve to a `ComponentType` from explicit or lexical scope.
5. Otherwise compilation raises the same positioned `MarkupSyntaxError` for an unknown tag.

`registry` and `primitives` cannot be supplied together, because their composition rules would be ambiguous. This is an additive API; calls using neither retain their existing behavior.

Text-content semantics and layout integer coercion moved from compiler tag-name branches to `ComponentContract.content_property` and `ComponentDefinition.markup_integer_properties`. `Text` and `Button` therefore retain their child-text diagnostics without a compiler-maintained component table.

## Cache isolation

Compiled templates use these cache identities:

- default built-ins: stable built-in registry version;
- legacy `primitives`: mapping identity, preserving the existing behavior;
- caller registry: registry object identity plus its version.

A successful registration increments the version, so compiling the same source after changing a registry produces a new template. Existing compiled templates retain their original immutable definition snapshot.

The static transform derives built-in tags from `builtin_component_registry()` instead of a hardcoded tag list. Its generated source, lexical scope rules and source-map output remain unchanged.
