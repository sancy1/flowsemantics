// Error hierarchy — mirrors python/src/flowsemantics/errors.

/** Base class for all FlowSemantics errors. */
export class FlowSemanticsError extends Error {
  constructor(message: string) {
    super(message);
    this.name = new.target.name;
  }
}

/** Structural error: invalid flow/IR construction (SPEC 4.3, 9.2). */
export class StructureError extends FlowSemanticsError {}
/** Evaluation error raised during rule evaluation. */
export class EvaluationError extends FlowSemanticsError {}
/** Portability error: contract cannot be exported to Portable IR (SPEC 14.2). */
export class PortabilityError extends FlowSemanticsError {}
/** Async-only contract used in a synchronous context (SPEC 11.7). */
export class AsyncOnlyContractError extends FlowSemanticsError {}
/** Raised when a replay record cannot be safely replayed (SPEC 12.6). */
export class ReplayError extends FlowSemanticsError {}

// Abstract error kinds (spec/fixtures.md) mapped to concrete classes.
/** Abstract error kind Kind.Timeout (spec/fixtures.md). */
export class KindTimeout extends Error { readonly kind = "Kind.Timeout"; }
/** Abstract error kind Kind.Cancelled (spec/fixtures.md). */
export class KindCancelled extends Error { readonly kind = "Kind.Cancelled"; }
/** Abstract error kind Kind.ValueError (spec/fixtures.md). */
export class KindValueError extends Error { readonly kind = "Kind.ValueError"; }
/** Abstract error kind Kind.Any (spec/fixtures.md). */
export class KindAny extends Error { readonly kind = "Kind.Any"; }

/** Create the concrete exception for an abstract error kind. */
export function exceptionForKind(kind: string): Error {
  switch (kind) {
    case "Kind.Timeout": return new KindTimeout(`fixture error: ${kind}`);
    case "Kind.Cancelled": return new KindCancelled(`fixture error: ${kind}`);
    case "Kind.ValueError": return new KindValueError(`fixture error: ${kind}`);
    case "Kind.Any":
    default: return new KindAny(`fixture error: ${kind}`);
  }
}

/** Return the abstract kind name for a concrete exception, or null if none. */
export function kindOfException(exc: unknown): string | null {
  if (exc instanceof KindTimeout) return "Kind.Timeout";
  if (exc instanceof KindCancelled) return "Kind.Cancelled";
  if (exc instanceof KindValueError) return "Kind.ValueError";
  if (exc instanceof KindAny) return "Kind.Any";
  return null;
}
