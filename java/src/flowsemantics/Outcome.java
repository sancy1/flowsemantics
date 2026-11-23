package flowsemantics;

import java.util.*;

/** Outcome model — SPEC 3.3-3.8, 7, 12.1. */
public final class Outcome {
    /** Terminal execution status (SPEC 3.1). */
    public enum ExecutionStatus { COMPLETED, FAILED, CANCELLED, TIMED_OUT }
    /** Decision status (SPEC 3.2). */
    public enum DecisionStatus { APPROVED, NO_MATCH }
    /** Rule evaluation mode (SPEC 10.6). */
    public enum EvaluationMode { FirstMatch, AllMatch, Priority }
    /** Finalizer failure policy (SPEC 16.3). */
    public enum FinallyFailurePolicy { PreservePrimary, Attach, ReplacePrimary }
    /** Interruption kind (SPEC 3.3). */
    public enum InterruptionKind { cancelled, timed_out }

    /** Interruption metadata recorded on an outcome (SPEC 3.3). */
    public static final class InterruptionInfo {
        /** Kind of interruption. */
        public final InterruptionKind kind;
        /** Source of the interruption. */
        public final String source;
        /** Wall-clock timestamp (epoch ms). */
        public final long timestamp;
        /** Create an InterruptionInfo. */
        public InterruptionInfo(InterruptionKind k, String s, long t) { kind = k; source = s; timestamp = t; }
    }

    /** Recovery metadata recorded when a catch rule recovers (SPEC 3.4). */
    public static final class RecoveryInfo {
        /** The original exception that was recovered. */
        public final Object originalException;
        /** Rule ID of the handler that recovered. */
        public final String handlerRuleId;
        /** Wall-clock timestamp of recovery (epoch ms). */
        public final long recoveredAt;
        /** Create a RecoveryInfo. */
        public RecoveryInfo(Object e, String id, long t) { originalException = e; handlerRuleId = id; recoveredAt = t; }
    }

    /** Finalization metadata recorded on an outcome (SPEC 3.5, 16.4). */
    public static final class FinalizationInfo {
        /** Whether all finalizers completed cleanly. */
        public final boolean isClean;
        /** Exceptions raised by finalizers. */
        public final List<Object> cleanupExceptions;
        /** Whether the cleanup budget was exceeded. */
        public final boolean cleanupBudgetExceeded;
        /** Cleanup budget used in milliseconds. */
        public final long cleanupBudgetUsedMs;
        /** Create a FinalizationInfo without budget info. */
        public FinalizationInfo(boolean c, List<Object> ex) {
            this(c, ex, false, 0);
        }
        /** Create a FinalizationInfo with budget info. */
        public FinalizationInfo(boolean c, List<Object> ex, boolean budgetExceeded, long budgetUsedMs) {
            isClean = c; cleanupExceptions = ex;
            cleanupBudgetExceeded = budgetExceeded; cleanupBudgetUsedMs = budgetUsedMs;
        }
    }

    /** A proposed effect — data only, never applied by the library (SPEC 3.7, 5). */
    public static final class Effect {
        /** Effect name. */
        public final String name;
        /** Effect payload. */
        public final Object payload;
        /** Create an Effect. */
        public Effect(String n, Object p) { name = n; payload = p; }
    }

    /** Diagnostic hook: receives each TraceEvent, may return extra fields (SPEC 12.2). */
    public interface DiagnosticHook { java.util.Map<String, Object> apply(TraceEvent event); }

    /** A single trace event (SPEC 3.8, 12.1). */
    public static final class TraceEvent {
        /** Event type (one of the 22-event vocabulary). */
        public final String type;
        /** Rule ID associated with the event, or null. */
        public final String ruleId;
        /** Skip/failure reason, or null. */
        public final String reason;
        /** Wall-clock timestamp (epoch ms). */
        public final long timestamp;
        /** Contract version stamped on the event. */
        public final String contractVersion;
        /** Optional diagnostics produced by the diagnostic hook. */
        public java.util.Map<String, Object> diagnostics;
        /** Create a TraceEvent. */
        public TraceEvent(String t, String r, String rs, long ts, String cv) {
            type = t; ruleId = r; reason = rs; timestamp = ts; contractVersion = cv;
        }
    }

    /** Collected execution trace (SPEC 3.8, 12.1-12.3). */
    public static final class ExecutionTrace {
        /** Emitted events in order. */
        public final List<TraceEvent> events = new ArrayList<>();
        /** Contract version stamped on every event. */
        public String contractVersion;
        /** Optional diagnostic hook invoked per event. */
        public DiagnosticHook diagnosticHook;
        /** Create an empty ExecutionTrace. */
        public ExecutionTrace() {}
        /** Create an ExecutionTrace with a contract version and hook. */
        public ExecutionTrace(String cv, DiagnosticHook hook) { contractVersion = cv; diagnosticHook = hook; }
        /** Emit a trace event, applying the diagnostic hook when present. */
        public void emit(String type, String ruleId, String reason, long ts) {
            TraceEvent e = new TraceEvent(type, ruleId, reason, ts, contractVersion);
            if (diagnosticHook != null) e.diagnostics = diagnosticHook.apply(e);
            events.add(e);
        }
    }

    /** The canonical outcome of a flow execution (SPEC 3.6, 7). */
    public static final class FlowOutcome {
        /** Terminal execution status. */
        public ExecutionStatus executionStatus;
        /** Decision status; null for recovered outcomes (SPEC 7). */
        public DecisionStatus decisionStatus;
        /** Produced value. */
        public Object value;
        /** Unrecovered primary exception, if any. */
        public Object primaryException;
        /** Recovery metadata when a catch rule recovered. */
        public RecoveryInfo recovery;
        /** Interruption metadata for CANCELLED/TIMED_OUT outcomes. */
        public InterruptionInfo interruption;
        /** Finalization metadata. */
        public FinalizationInfo finalization;
        /** Secondary exceptions isolated from hooks/finalizers. */
        public List<Object> secondaryExceptions = new ArrayList<>();
        /** Proposed effects in evaluation order. */
        public List<Effect> effects = new ArrayList<>();
        /** Execution trace when tracing was enabled. */
        public ExecutionTrace trace;
    }

    /** Create a COMPLETED + APPROVED outcome. */
    public static FlowOutcome completed(Object value) {
        FlowOutcome o = new FlowOutcome();
        o.executionStatus = ExecutionStatus.COMPLETED;
        o.decisionStatus = DecisionStatus.APPROVED;
        o.value = value;
        return o;
    }

    /** Create a COMPLETED + NO_MATCH outcome. */
    public static FlowOutcome noMatch(Object value) {
        FlowOutcome o = new FlowOutcome();
        o.executionStatus = ExecutionStatus.COMPLETED;
        o.decisionStatus = DecisionStatus.NO_MATCH;
        o.value = value;
        return o;
    }

    /** Create a FAILED outcome carrying the primary exception. */
    public static FlowOutcome failed(Object exc) {
        FlowOutcome o = new FlowOutcome();
        o.executionStatus = ExecutionStatus.FAILED;
        o.primaryException = exc;
        return o;
    }
}
