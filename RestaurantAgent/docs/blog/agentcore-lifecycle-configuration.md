---
title: "Controlling AgentCore Session Timeout & Max Lifetime with boto3 and the agentcore CLI"
date: 2026-07-10
id: blog0539
tag: aws, bedrock, agentcore, boto3, cdk
img: aws
toc: true
intro: "A practical guide to configuring AgentCore runtime lifecycle settings, idle session timeout and max instance lifetime, using the boto3 control client, CDK constructs, and workarounds for the agentcore CLI."
indent: true
wip: false
---

<style>
  img {
    max-width: 660px !important;
  }
  table td:first-child, table th:first-child {
    min-width: 200px;
  }
</style>

### Introduction {#introduction}

AgentCore runs every session inside a dedicated microVM. Two parameters in `LifecycleConfiguration` control how long that microVM lives:

- `idleRuntimeSessionTimeout`, seconds of inactivity before the microVM is torn down. Default 900 (15 min). Range 60–28,800.
- `maxLifetime`, hard ceiling on a microVM's lifespan, counting from creation. Default 28,800 (8 hours). Range 60–28,800.

Constraint: `idleRuntimeSessionTimeout` ≤ `maxLifetime`.

### How Lifecycle Works {#how-lifecycle-works}

Each unique `runtimeSessionId` gets its own microVM with independent timers. The idle timer resets on every invocation; the max lifetime timer never resets.

In AG-UI agents (the `StrandsAgent` with `POST /invocations`), the frontend sends a `threadId` inside `RunAgentInput`. The platform maps it to `runtimeSessionId` automatically, see [Building a Chatbot with Strands Agents and the AG-UI Protocol](/blog/article/Building-a-Chatbot-with-Strands-Agents-and-the-AG-UI-Protocol#3.-the-ag-ui-protocol) for the full protocol flow. Distinct `threadId` → distinct microVM. Same `threadId` → same microVM, idle timer resets on each call.

### Cost Impact of Lifecycle Settings {#cost-impact}

#### Demo Calculation

AgentCore Runtime charges for actual CPU consumption (\$0.0895/vCPU-hour) and peak memory (\$0.00945/GB-hour) in per-second increments. I/O wait time is free. The idle timeout directly controls how long a microVM lingers after the user stops interacting, and every second the VM sits idle, we pay for memory.

Consider a RestaurantAgent handling 100 conversations per day. Each conversation lasts 2 minutes of active back-and-forth, and uses 0.5 GB of memory with CPU active 30% of the time. The idle timeout controls the tail:

| Setting | Session lifetime | CPU cost/session | Memory cost/session | Monthly cost (3,000 sessions) |
|---|---|---|---|---|
| Default (15 min idle) | 17 min | $0.0076 | $0.0013 | $26.70 |
| Tuned (5 min idle) | 7 min | $0.0031 | $0.0005 | $10.80 |
| Aggressive (1 min idle) | 3 min | $0.0013 | $0.0002 | $4.50 |

Calculation for the default row:

```
CPU:  17 min × 60s × 0.30 active × 1 vCPU × $0.0895/3600 = $0.0076
Mem:  17 min × 60s × 0.5 GB × $0.00945/3600          = $0.0013
Total per session: $0.0089
Monthly: 100 sessions/day × 30 days × $0.0089 = $26.70
```

Dropping the idle timeout from 15 minutes to 5 minutes cuts the monthly bill by 60%, from \$26.70 to $10.80. The `maxLifetime` setting caps this further: without it, a session that receives a stray keep-alive call could live for the full 8-hour default.

The savings scale linearly with session count. At 10,000 conversations per day, the difference between default and tuned is roughly \$1,590/month vs. \$630/month.

#### AWS Documentations

- [Amazon Bedrock AgentCore Pricing](https://aws.amazon.com/bedrock/agentcore/pricing/) 

- [AWS blog: AgentCore Runtime cost example](https://aws.amazon.com/blogs/machine-learning/securely-launch-and-scale-your-agents-and-tools-on-amazon-bedrock-agentcore-runtime/).

### Setting Lifecycle Configuration {#setting-lifecycle-configuration}

Once we know what values we want, we need to apply them to a runtime.

#### CDK Entrypoint (Recommended) {#method-1-cdk-entrypoint}

The `AgentCoreProjectSpec` interface in `@aws/agentcore-cdk` accepts `lifecycleConfiguration` per runtime, even though the CLI-authored `agentcore.json` does not yet expose it. The fix is a few lines in `agentcore/cdk/bin/cdk.ts`, inserted before `new AgentCoreStack(...)`.

The scaffolded file already declares `const specAny = spec as any;` around line 35. We reuse that variable — do not redeclare it. Insert the patch right before the stack instantiation:

```typescript
// agentcore/cdk/bin/cdk.ts — insert before `new AgentCoreStack(app, stackName, {`

// Patch lifecycle configuration onto every runtime
const runtimesWithLifecycle = specAny.runtimes.map((rt: any) => ({
  ...rt,
  lifecycleConfiguration: {
    idleRuntimeSessionTimeout: 300,  // 5 minutes
    maxLifetime: 14400,              // 4 hours
  },
}));
const patchedSpec = { ...specAny, runtimes: runtimesWithLifecycle };

// Then change `spec` to `spec: patchedSpec` in the existing stack props:
new AgentCoreStack(app, stackName, {
  spec: patchedSpec,               // was: spec
  mcpSpec,
  credentials,
  connectorParametersByFile,
  harnesses: harnessConfigs.length > 0 ? harnessConfigs : undefined,
  paymentSpec,
  env,
  description: `AgentCore stack for ${spec.name} deployed to ${target.name} (${target.region})`,
  tags: {
    'agentcore:project-name': spec.name,
    'agentcore:target-name': target.name,
  },
});
```

Two changes: insert the patch block, and change `spec` to `spec: patchedSpec`. That's it. Run `agentcore deploy` and the lifecycle settings are applied.

`AgentCoreStack` (our project-local wrapper at `agentcore/cdk/lib/cdk-stack.ts`, scaffolded by `agentcore init`) receives the already-patched `spec` and passes it straight through to `AgentCoreApplication`, the L3 construct from `@aws/agentcore-cdk`. No changes needed in the stack class.

![](/assets/img/2026-07-11-03-23-49.png)

#### boto3 Control Client (Alternative) {#method-2-boto3-control-client}

If redeploying via CDK is not an option, we can patch a running runtime directly through the `bedrock-agentcore-control` API. The `update_agent_runtime` call requires re-declaring `agentRuntimeArtifact`, `roleArn`, and `networkConfiguration` alongside the new `lifecycleConfiguration`. The safest approach is to read the current runtime first, then pass everything back unchanged except the lifecycle block:

```python
import boto3

control = boto3.client("bedrock-agentcore-control", region_name="us-east-1")
RUNTIME_ID = "RestaurantAgent_MyRestaurantAgent-dqQ1m6Bgn4"

try:
    current = control.get_agent_runtime(agentRuntimeId=RUNTIME_ID)

    response = control.update_agent_runtime(
        agentRuntimeId=RUNTIME_ID,
        agentRuntimeArtifact=current["agentRuntimeArtifact"],
        roleArn=current["roleArn"],
        networkConfiguration=current["networkConfiguration"],
        lifecycleConfiguration={
            "idleRuntimeSessionTimeout": 300,
            "maxLifetime": 14400
        }
    )
    new_lc = response.get("lifecycleConfiguration", {})
    print(f"Updated. idle={new_lc.get('idleRuntimeSessionTimeout')}s, max={new_lc.get('maxLifetime')}s")

except control.exceptions.ValidationException as e:
    print(f"Validation error: {e}")
except control.exceptions.ResourceNotFoundException:
    print(f"Runtime '{RUNTIME_ID}' not found.")
```

Validation: both values 60–28,800, and idle ≤ max. Caveat: a subsequent `cdk deploy` that regenerates the template without `LifecycleConfiguration` may reset these. Prefer the CDK entrypoint approach when possible.

#### agentcore CLI {#method-3-agentcore-cli}

The current `agentcore.json` schema (v1) does not include `lifecycleConfiguration` in `AgentEnvSpec`. Adding it to the JSON will be ignored or rejected by the CLI. Use the CDK entrypoint approach above: patch `bin/cdk.ts`, then `agentcore deploy` (which invokes CDK under the hood). The AgentCore team has exposed `lifecycleConfiguration` at every other layer; it is likely to land in the `agentcore.json` schema in a future revision.

### Quick Reference {#quick-reference}

| Parameter | Min | Max | Default |
|---|---|---|---|
| `idleRuntimeSessionTimeout` | 60s | 28,800s (8h) | 900s (15 min) |
| `maxLifetime` | 60s | 28,800s (8h) | 28,800s (8h) |

>> **Constraint:** `idleRuntimeSessionTimeout` ≤ `maxLifetime`.

| Environment | idleTimeout | maxLifetime |
|---|---|---|
| Dev / test | 60–180s | 600–1,800s |
| Production (stateless) | 120–300s | 3,600–7,200s |
| Production (conversational) | 900–1,800s | 14,400–28,800s |
| Batch / eval | 60s | 60s |


### Conclusion ans Reference from AWS Documentation {#conclusion}

The fastest path for an existing CLI-deployed runtime is the read-before-write boto3 script from [$method-1-boto3-control-client]. It takes under a minute and applies immediately. When lifecycle configuration lands in the CLI schema, migrate it into `agentcore.json`.

See also: 
- [Configure Amazon Bedrock AgentCore lifecycle settings](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-lifecycle-settings.html)

- [UpdateAgentRuntime API reference](https://docs.aws.amazon.com/bedrock-agentcore-control/latest/APIReference/API_UpdateAgentRuntime.html).
