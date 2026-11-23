package flowsemantics

import "fmt"

// FlowSemanticsError is the base error type.
type FlowSemanticsError struct{ msg string }

func (e *FlowSemanticsError) Error() string { return e.msg }

// NewStructureError creates a structural error: invalid flow/IR construction
// (SPEC 4.3, 9.2).
func NewStructureError(msg string) *FlowSemanticsError {
	return &FlowSemanticsError{msg: "structure: " + msg}
}

// Abstract error kinds (spec/fixtures.md).
type KindTimeout struct{ FlowSemanticsError }

// KindCancelled is the abstract Kind.Cancelled error kind.
type KindCancelled struct{ FlowSemanticsError }

// KindValueError is the abstract Kind.ValueError error kind.
type KindValueError struct{ FlowSemanticsError }

// KindAny is the abstract Kind.Any error kind.
type KindAny struct{ FlowSemanticsError }

// NewKindTimeout creates a Kind.Timeout error.
func NewKindTimeout(msg string) *KindTimeout {
	return &KindTimeout{FlowSemanticsError{msg: "Kind.Timeout: " + msg}}
}
// NewKindCancelled creates a Kind.Cancelled error.
func NewKindCancelled(msg string) *KindCancelled {
	return &KindCancelled{FlowSemanticsError{msg: "Kind.Cancelled: " + msg}}
}
// NewKindValueError creates a Kind.ValueError error.
func NewKindValueError(msg string) *KindValueError {
	return &KindValueError{FlowSemanticsError{msg: "Kind.ValueError: " + msg}}
}
// NewKindAny creates a Kind.Any error.
func NewKindAny(msg string) *KindAny {
	return &KindAny{FlowSemanticsError{msg: "Kind.Any: " + msg}}
}

// ExceptionForKind creates the concrete exception for an abstract error kind.
func ExceptionForKind(kind string) error {
	switch kind {
	case "Kind.Timeout":
		return NewKindTimeout("fixture error")
	case "Kind.Cancelled":
		return NewKindCancelled("fixture error")
	case "Kind.ValueError":
		return NewKindValueError("fixture error")
	default:
		return NewKindAny(kind)
	}
}

// KindOfException returns the abstract kind name for a concrete exception,
// or "" if none.
func KindOfException(exc any) string {
	switch exc.(type) {
	case *KindTimeout:
		return "Kind.Timeout"
	case *KindCancelled:
		return "Kind.Cancelled"
	case *KindValueError:
		return "Kind.ValueError"
	case *KindAny:
		return "Kind.Any"
	}
	return ""
}

var _ = fmt.Sprintf // keep fmt import if unused elsewhere
