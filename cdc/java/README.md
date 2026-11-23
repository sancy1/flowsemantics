# Consumer-Driven Contract Tests — Java

Tests written purely from the public documentation, compiled and run against
**only the published artifact** — never the source tree.

## Pre-publish (local jar)

```bash
# Build the library jar once (from repo root):
cd java
javac -d out src/flowsemantics/*.java src/flowsemantics/runner/*.java
jar --create --file flowsemantics.jar -C out .

# Run the consumer tests:
cd ../cdc/java
javac -cp ../../java/flowsemantics.jar ConsumerTest.java
java -cp .;../../java/flowsemantics.jar ConsumerTest
```

Expected: `passed=79 failed=0`

## Post-publish (Maven Central)

Replace the classpath jar with the published coordinates:

```xml
<dependency>
  <groupId>com.flowsemantics</groupId>
  <artifactId>flowsemantics</artifactId>
  <version>0.1.0</version>
</dependency>
```

## Coverage

All 62 SPEC features: core decision layer (when/whenNot/otherwise/default,
evaluation modes, guard, priority, effects, merge, decision tables, hit
policies, RuleId uniqueness, effective dates), error & execution layer
(typed/when/any catch, rethrow, hooks, cancellation, timeout, finally
policies, secondary exceptions, interruption model, finally context), trust
semantics (trace vocabulary, diagnostic hook, explain, simulate, replay
record/modes, HMAC integrity, fail-closed, shadow, validate, contract
version, deterministic replay), and portable IR (PExpr ops, serialization,
whenExpr/whenNotExpr, fromIr, IR limits, flow_id, contract_version).
