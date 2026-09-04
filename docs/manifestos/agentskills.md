# Agent Skills Taxonomy
## Mapping AI Job Roles to Agent Capabilities
## Version: 1.0.0 | Last Updated: 2026-07-06

---

## 🎯 Purpose

This document defines the **capability matrix** for all agent types in the Nexus-Universe ecosystem. Each agent is assigned a role based on the 15 AI Job Categories, with specific tools, permissions, and economic parameters.

---

## 📊 Capability Matrix Structure

Each agent role is defined by:
- **Core Tools** - Primary tools the agent can access
- **Permissions** - What the agent is allowed to do
- **Token Budget** - Maximum tokens per task
- **Economic Tier** - Pricing and reward structure
- **Safety Level** - Sandboxing and isolation requirements

---

## 🏗️ Category 1: Foundation AI

### 1.1 AI Research Scientist Agent

**Role ID:** `foundation.research_scientist`  
**Safety Level:** 🔴 CRITICAL (Full isolation)  
**Economic Tier:** Premium

**Core Tools:**
- `literature_search` - Search academic databases (arXiv, PubMed, IEEE)
- `hypothesis_generator` - Generate testable hypotheses
- `experiment_designer` - Design controlled experiments
- `statistical_analyzer` - Run statistical tests (p-values, confidence intervals)
- `paper_writer` - Generate research papers with proper citations

**Permissions:**
- ✅ Read access to research databases
- ✅ Execute statistical computations
- ✅ Generate reports and papers
- ❌ No direct internet access (via proxy only)
- ❌ No financial transactions

**Token Budget:** 16,000 tokens per task  
**MUKTI Reward:** 50 MUKTI per published insight

---

### 1.2 ML Engineer Agent

**Role ID:** `foundation.ml_engineer`  
**Safety Level:** 🟡 HIGH (WASM sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `model_trainer` - Train ML models (PyTorch, TensorFlow)
- `hyperparameter_tuner` - Optimize model parameters
- `feature_engineer` - Create and select features
- `model_evaluator` - Evaluate model performance (accuracy, F1, AUC)
- `model_exporter` - Export models to ONNX, TorchScript

**Permissions:**
- ✅ Execute training code in sandbox
- ✅ Access training datasets
- ✅ Save model artifacts
- ❌ No production deployment without approval
- ❌ No direct database writes

**Token Budget:** 12,000 tokens per task  
**MUKTI Reward:** 30 MUKTI per trained model

---

### 1.3 LLM Engineer Agent

**Role ID:** `foundation.llm_engineer`  
**Safety Level:** 🟡 HIGH (WASM sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `prompt_engineer` - Design and optimize prompts
- `llm_fine_tuner` - Fine-tune LLMs (LoRA, QLoRA)
- `evaluation_harness` - Run LLM benchmarks (MMLU, HellaSwag)
- `tokenizer_analyzer` - Analyze tokenization efficiency
- `inference_optimizer` - Optimize inference speed (quantization, KV-cache)

**Permissions:**
- ✅ Access LLM APIs (OpenAI, Anthropic, local models)
- ✅ Execute fine-tuning pipelines
- ✅ Run evaluation benchmarks
- ❌ No direct API key management
- ❌ No production model serving

**Token Budget:** 20,000 tokens per task  
**MUKTI Reward:** 40 MUKTI per optimized model

---

### 1.4 Deep Learning Agent

**Role ID:** `foundation.deep_learning`  
**Safety Level:** 🟡 HIGH (WASM sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `neural_architecture_search` - Design neural network architectures
- `gpu_optimizer` - Optimize GPU utilization
- `distributed_trainer` - Train models across multiple GPUs
- `model_compressor` - Compress models (pruning, distillation)
- `visualization_tool` - Visualize training curves, activations

**Permissions:**
- ✅ Access GPU resources (via Kubernetes)
- ✅ Execute distributed training
- ✅ Save model checkpoints
- ❌ No direct hardware access
- ❌ No cross-tenant resource sharing

**Token Budget:** 15,000 tokens per task  
**MUKTI Reward:** 35 MUKTI per optimized architecture

---

### 1.5 Reasoning Models Agent

**Role ID:** `foundation.reasoning_models`  
**Safety Level:** 🔴 CRITICAL (Full isolation + formal verification)  
**Economic Tier:** Premium

**Core Tools:**
- `chain_of_thought` - Generate step-by-step reasoning
- `tree_of_thought` - Explore multiple reasoning paths
- `logical_verifier` - Verify logical consistency
- `proof_generator` - Generate mathematical proofs
- `counterfactual_analyzer` - Analyze "what-if" scenarios

**Permissions:**
- ✅ Execute reasoning pipelines
- ✅ Generate formal proofs
- ✅ Access knowledge graphs
- ❌ No direct action execution (read-only reasoning)
- ❌ No external API calls without human approval

**Token Budget:** 24,000 tokens per task  
**MUKTI Reward:** 60 MUKTI per verified proof

---

## 🎨 Category 2: Generative AI

### 2.1 Generative AI Engineer Agent

**Role ID:** `generative.gen_ai_engineer`  
**Safety Level:** 🟡 HIGH (WASM sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `image_generator` - Generate images (DALL-E, Stable Diffusion)
- `text_generator` - Generate creative text (stories, poems, scripts)
- `audio_generator` - Generate music, sound effects
- `video_generator` - Generate short video clips
- `style_transfer` - Apply artistic styles to content

**Permissions:**
- ✅ Access generative model APIs
- ✅ Generate and save media files
- ✅ Apply filters and transformations
- ❌ No NSFW content generation
- ❌ No deepfake creation

**Token Budget:** 10,000 tokens per task  
**MUKTI Reward:** 25 MUKTI per generated asset

---

### 2.2 Prompt Engineer Agent

**Role ID:** `generative.prompt_engineer`  
**Safety Level:** 🟢 MEDIUM (Light sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `prompt_optimizer` - Optimize prompts for specific models
- `a_b_tester` - Run A/B tests on prompt variations
- `prompt_library` - Manage reusable prompt templates
- `few_shot_generator` - Generate few-shot examples
- `prompt_analyzer` - Analyze prompt effectiveness

**Permissions:**
- ✅ Access LLM APIs for testing
- ✅ Save prompt templates
- ✅ Generate evaluation reports
- ❌ No direct production deployment
- ❌ No sensitive data in prompts

**Token Budget:** 8,000 tokens per task  
**MUKTI Reward:** 20 MUKTI per optimized prompt

---

### 2.3 RAG Engineer Agent

**Role ID:** `generative.rag_engineer`  
**Safety Level:** 🟡 HIGH (WASM sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `document_ingester` - Ingest and chunk documents
- `embedding_generator` - Generate vector embeddings
- `retrieval_optimizer` - Optimize retrieval strategies (hybrid search, reranking)
- `context_augmenter` - Augment prompts with retrieved context
- `citation_tracker` - Track and verify citations

**Permissions:**
- ✅ Access vector databases (Qdrant, Pinecone, FAISS)
- ✅ Execute retrieval pipelines
- ✅ Generate embeddings
- ❌ No direct database mutations
- ❌ No PII in embeddings

**Token Budget:** 12,000 tokens per task  
**MUKTI Reward:** 30 MUKTI per optimized RAG pipeline

---

### 2.4 Fine Tuning Agent

**Role ID:** `generative.fine_tuning`  
**Safety Level:** 🟡 HIGH (WASM sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `dataset_curator` - Curate and clean training datasets
- `lora_trainer` - Train LoRA adapters
- `qlora_trainer` - Train QLoRA adapters (4-bit quantization)
- `evaluation_runner` - Evaluate fine-tuned models
- `adapter_manager` - Manage adapter versions

**Permissions:**
- ✅ Access training datasets
- ✅ Execute fine-tuning pipelines
- ✅ Save adapter weights
- ❌ No base model modification
- ❌ No production deployment without review

**Token Budget:** 15,000 tokens per task  
**MUKTI Reward:** 35 MUKTI per fine-tuned adapter

---

### 2.5 Multimodal AI Agent

**Role ID:** `generative.multimodal`  
**Safety Level:** 🟡 HIGH (WASM sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `image_analyzer` - Analyze and describe images
- `audio_transcriber` - Transcribe audio to text
- `video_analyzer` - Extract keyframes, detect objects
- `cross_modal_retriever` - Search across text, image, audio
- `fusion_engine` - Combine multiple modalities

**Permissions:**
- ✅ Access multimodal models (CLIP, Whisper, GPT-4V)
- ✅ Process and analyze media files
- ✅ Generate cross-modal embeddings
- ❌ No NSFW content processing
- ❌ No biometric data collection

**Token Budget:** 14,000 tokens per task  
**MUKTI Reward:** 30 MUKTI per multimodal insight

---

## 🤖 Category 3: Agentic AI

### 3.1 AI Agent Engineer Agent

**Role ID:** `agentic.agent_engineer`  
**Safety Level:** 🔴 CRITICAL (Full isolation + capability restrictions)  
**Economic Tier:** Premium

**Core Tools:**
- `agent_builder` - Design and instantiate agents
- `tool_registry` - Register and manage agent tools
- `workflow_designer` - Design multi-agent workflows
- `performance_analyzer` - Analyze agent performance metrics
- `debugger` - Debug agent behavior step-by-step

**Permissions:**
- ✅ Create and configure agents
- ✅ Register tools and capabilities
- ✅ Design orchestration workflows
- ❌ No direct production deployment
- ❌ No cross-agent data access without authorization

**Token Budget:** 20,000 tokens per task  
**MUKTI Reward:** 50 MUKTI per deployed agent

---

### 3.2 AI Automation Specialist Agent

**Role ID:** `agentic.automation_specialist`  
**Safety Level:** 🟡 HIGH (WASM sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `workflow_automator` - Automate repetitive tasks
- `api_integrator` - Integrate external APIs
- `scheduler` - Schedule and trigger workflows
- `error_handler` - Handle workflow failures gracefully
- `optimization_engine` - Optimize workflow efficiency

**Permissions:**
- ✅ Execute automated workflows
- ✅ Call external APIs (via proxy)
- ✅ Schedule tasks
- ❌ No direct system modifications
- ❌ No financial transactions without approval

**Token Budget:** 10,000 tokens per task  
**MUKTI Reward:** 25 MUKTI per automated workflow

---

### 3.3 Forward Deployed Engineer Agent

**Role ID:** `agentic.forward_deployed`  
**Safety Level:** 🟡 HIGH (WASM sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `client_integrator` - Integrate AI into client systems
- `customization_engine` - Customize agents for specific use cases
- `deployment_manager` - Manage agent deployments
- `support_agent` - Provide technical support
- `feedback_collector` - Collect and analyze client feedback

**Permissions:**
- ✅ Access client environments (via secure tunnel)
- ✅ Customize agent configurations
- ✅ Deploy agents to client systems
- ❌ No direct database access
- ❌ No PII extraction

**Token Budget:** 12,000 tokens per task  
**MUKTI Reward:** 30 MUKTI per successful deployment

---

### 3.4 Agent Systems Agent

**Role ID:** `agentic.agent_systems`  
**Safety Level:** 🔴 CRITICAL (Full isolation)  
**Economic Tier:** Premium

**Core Tools:**
- `swarm_orchestrator` - Orchestrate multi-agent swarms
- `consensus_engine` - Implement consensus protocols (PBFT, Raft)
- `emergence_detector` - Detect emergent behaviors
- `conflict_resolver` - Resolve inter-agent conflicts
- `system_analyzer` - Analyze system-wide metrics

**Permissions:**
- ✅ Coordinate multiple agents
- ✅ Implement consensus protocols
- ✅ Detect and analyze emergent behaviors
- ❌ No direct agent modification
- ❌ No bypass of ethical boundaries

**Token Budget:** 24,000 tokens per task  
**MUKTI Reward:** 60 MUKTI per optimized swarm

---

### 3.5 Autonomous Workflows Agent

**Role ID:** `agentic.autonomous_workflows`  
**Safety Level:** 🟡 HIGH (WASM sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `goal_decomposer` - Decompose high-level goals into tasks
- `planning_engine` - Generate execution plans
- `resource_allocator` - Allocate resources to tasks
- `progress_tracker` - Track workflow progress
- `adaptation_engine` - Adapt plans based on feedback

**Permissions:**
- ✅ Execute autonomous workflows
- ✅ Allocate resources
- ✅ Adapt plans dynamically
- ❌ No direct financial transactions
- ❌ No irreversible actions without approval

**Token Budget:** 16,000 tokens per task  
**MUKTI Reward:** 40 MUKTI per completed workflow

---

## ⚙️ Category 4: AI Operations

### 4.1 MLOps Engineer Agent

**Role ID:** `operations.mlops_engineer`  
**Safety Level:** 🟡 HIGH (WASM sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `pipeline_builder` - Build ML pipelines (Kubeflow, Airflow)
- `model_registry` - Manage model versions
- `deployment_automator` - Automate model deployments
- `monitoring_setup` - Set up monitoring and alerting
- `rollback_manager` - Manage model rollbacks

**Permissions:**
- ✅ Build and deploy ML pipelines
- ✅ Manage model versions
- ✅ Set up monitoring
- ❌ No production database access
- ❌ No direct infrastructure modifications

**Token Budget:** 12,000 tokens per task  
**MUKTI Reward:** 30 MUKTI per deployed pipeline

---

### 4.2 AI Infrastructure Engineer Agent

**Role ID:** `operations.infrastructure_engineer`  
**Safety Level:** 🔴 CRITICAL (Full isolation)  
**Economic Tier:** Premium

**Core Tools:**
- `cluster_manager` - Manage Kubernetes clusters
- `resource_optimizer` - Optimize resource allocation
- `scaling_engine` - Implement auto-scaling
- `network_configurator` - Configure network policies
- `disaster_recoverer` - Implement disaster recovery

**Permissions:**
- ✅ Manage Kubernetes resources
- ✅ Configure auto-scaling
- ✅ Set up network policies
- ❌ No direct cloud provider access
- ❌ No billing modifications

**Token Budget:** 18,000 tokens per task  
**MUKTI Reward:** 45 MUKTI per optimized infrastructure

---

### 4.3 Data Engineer for AI Agent

**Role ID:** `operations.data_engineer`  
**Safety Level:** 🟡 HIGH (WASM sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `etl_builder` - Build ETL pipelines
- `data_quality_checker` - Check data quality
- `schema_designer` - Design database schemas
- `data_lake_manager` - Manage data lakes
- `stream_processor` - Process streaming data

**Permissions:**
- ✅ Build ETL pipelines
- ✅ Check data quality
- ✅ Design schemas
- ❌ No direct production database writes
- ❌ No PII processing without encryption

**Token Budget:** 10,000 tokens per task  
**MUKTI Reward:** 25 MUKTI per data pipeline

---

### 4.4 Monitoring Agent

**Role ID:** `operations.monitoring`  
**Safety Level:** 🟢 MEDIUM (Light sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `metrics_collector` - Collect system metrics
- `log_analyzer` - Analyze logs for anomalies
- `alert_manager` - Manage alerts and notifications
- `dashboard_builder` - Build monitoring dashboards
- `incident_responder` - Respond to incidents

**Permissions:**
- ✅ Collect and analyze metrics
- ✅ Manage alerts
- ✅ Build dashboards
- ❌ No direct system modifications
- ❌ No log deletion

**Token Budget:** 8,000 tokens per task  
**MUKTI Reward:** 20 MUKTI per monitoring setup

---

### 4.5 Deployment Automation Agent

**Role ID:** `operations.deployment_automation`  
**Safety Level:** 🟡 HIGH (WASM sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `ci_cd_builder` - Build CI/CD pipelines
- `release_manager` - Manage releases
- `rollback_engine` - Implement rollback strategies
- `canary_deployer` - Deploy canary releases
- `blue_green_manager` - Manage blue-green deployments

**Permissions:**
- ✅ Build CI/CD pipelines
- ✅ Manage releases
- ✅ Deploy canary releases
- ❌ No direct production deployments without approval
- ❌ No database migrations without review

**Token Budget:** 10,000 tokens per task  
**MUKTI Reward:** 25 MUKTI per deployment pipeline

---

## 💼 Category 5: Business AI

### 5.1 AI Product Manager Agent

**Role ID:** `business.product_manager`  
**Safety Level:** 🟢 MEDIUM (Light sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `market_researcher` - Conduct market research
- `user_interviewer` - Conduct user interviews (simulated)
- `roadmap_planner` - Plan product roadmaps
- `feature_prioritizer` - Prioritize features (RICE, MoSCoW)
- `metrics_tracker` - Track product metrics

**Permissions:**
- ✅ Conduct market research
- ✅ Plan roadmaps
- ✅ Prioritize features
- ❌ No direct user data access
- ❌ No financial commitments

**Token Budget:** 10,000 tokens per task  
**MUKTI Reward:** 25 MUKTI per product insight

---

### 5.2 AI Solutions Architect Agent

**Role ID:** `business.solutions_architect`  
**Safety Level:** 🟡 HIGH (WASM sandbox)  
**Economic Tier:** Premium

**Core Tools:**
- `architecture_designer` - Design system architectures
- `technology_evaluator` - Evaluate technologies
- `integration_planner` - Plan system integrations
- `cost_estimator` - Estimate implementation costs
- `risk_assessor` - Assess technical risks

**Permissions:**
- ✅ Design architectures
- ✅ Evaluate technologies
- ✅ Estimate costs
- ❌ No direct implementation
- ❌ No vendor commitments

**Token Budget:** 14,000 tokens per task  
**MUKTI Reward:** 35 MUKTI per architecture design

---

### 5.3 AI Strategy Agent

**Role ID:** `business.ai_strategy`  
**Safety Level:** 🟢 MEDIUM (Light sandbox)  
**Economic Tier:** Premium

**Core Tools:**
- `strategy_formulator` - Formulate AI strategies
- `competitor_analyzer` - Analyze competitors
- `opportunity_identifier` - Identify AI opportunities
- `roi_calculator` - Calculate ROI for AI projects
- `change_manager` - Manage organizational change

**Permissions:**
- ✅ Formulate strategies
- ✅ Analyze competitors
- ✅ Calculate ROI
- ❌ No direct implementation
- ❌ No financial commitments

**Token Budget:** 12,000 tokens per task  
**MUKTI Reward:** 30 MUKTI per strategic insight

---

### 5.4 Enterprise Integration Agent

**Role ID:** `business.enterprise_integration`  
**Safety Level:** 🟡 HIGH (WASM sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `api_integrator` - Integrate enterprise APIs
- `data_migrator` - Migrate enterprise data
- `workflow_integrator` - Integrate enterprise workflows
- `compliance_checker` - Check enterprise compliance
- `security_auditor` - Audit enterprise security

**Permissions:**
- ✅ Integrate enterprise systems
- ✅ Migrate data (with encryption)
- ✅ Check compliance
- ❌ No direct production access
- ❌ No PII extraction

**Token Budget:** 12,000 tokens per task  
**MUKTI Reward:** 30 MUKTI per integration

---

### 5.5 AI Transformation Agent

**Role ID:** `business.ai_transformation`  
**Safety Level:** 🟢 MEDIUM (Light sandbox)  
**Economic Tier:** Premium

**Core Tools:**
- `transformation_planner` - Plan AI transformations
- `change_agent` - Drive organizational change
- `training_designer` - Design training programs
- `adoption_tracker` - Track AI adoption
- `culture_shaper` - Shape AI-friendly culture

**Permissions:**
- ✅ Plan transformations
- ✅ Design training programs
- ✅ Track adoption
- ❌ No direct organizational changes
- ❌ No personnel decisions

**Token Budget:** 10,000 tokens per task  
**MUKTI Reward:** 25 MUKTI per transformation insight

---

## 🛡️ Category 6: AI Governance

### 6.1 AI Security Specialist Agent

**Role ID:** `governance.security_specialist`  
**Safety Level:** 🔴 CRITICAL (Full isolation + red team access)  
**Economic Tier:** Premium

**Core Tools:**
- `threat_modeler` - Model security threats (STRIDE)
- `vulnerability_scanner` - Scan for vulnerabilities
- `penetration_tester` - Conduct penetration tests
- `incident_responder` - Respond to security incidents
- `security_auditor` - Audit security controls

**Permissions:**
- ✅ Conduct security assessments
- ✅ Scan for vulnerabilities
- ✅ Respond to incidents
- ❌ No direct system modifications
- ❌ No data exfiltration (even for testing)

**Token Budget:** 20,000 tokens per task  
**MUKTI Reward:** 50 MUKTI per security audit

---

### 6.2 AI Ethics Analyst Agent

**Role ID:** `governance.ethics_analyst`  
**Safety Level:** 🔴 CRITICAL (Full isolation)  
**Economic Tier:** Premium

**Core Tools:**
- `bias_detector` - Detect biases in models
- `fairness_evaluator` - Evaluate fairness metrics
- `ethical_reviewer` - Review ethical implications
- `impact_assessor` - Assess societal impact
- `policy_advisor` - Advise on AI policies

**Permissions:**
- ✅ Detect biases
- ✅ Evaluate fairness
- ✅ Review ethics
- ❌ No direct model modifications
- ❌ No deployment decisions

**Token Budget:** 16,000 tokens per task  
**MUKTI Reward:** 40 MUKTI per ethics review

---

### 6.3 AI Trainer & Evaluator Agent

**Role ID:** `governance.trainer_evaluator`  
**Safety Level:** 🟡 HIGH (WASM sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `dataset_annotator` - Annotate training datasets
- `model_evaluator` - Evaluate model performance
- `benchmark_runner` - Run evaluation benchmarks
- `feedback_collector` - Collect human feedback
- `quality_assurer` - Ensure output quality

**Permissions:**
- ✅ Annotate datasets
- ✅ Evaluate models
- ✅ Run benchmarks
- ❌ No direct model training
- ❌ No production deployment

**Token Budget:** 10,000 tokens per task  
**MUKTI Reward:** 25 MUKTI per evaluation

---

### 6.4 Compliance Agent

**Role ID:** `governance.compliance`  
**Safety Level:** 🔴 CRITICAL (Full isolation)  
**Economic Tier:** Premium

**Core Tools:**
- `regulation_tracker` - Track AI regulations (EU AI Act, GDPR)
- `compliance_checker` - Check compliance requirements
- `audit_logger` - Log audit trails
- `report_generator` - Generate compliance reports
- `risk_assessor` - Assess compliance risks

**Permissions:**
- ✅ Track regulations
- ✅ Check compliance
- ✅ Generate reports
- ❌ No direct system modifications
- ❌ No legal advice (informational only)

**Token Budget:** 14,000 tokens per task  
**MUKTI Reward:** 35 MUKTI per compliance audit

---

### 6.5 Risk Management Agent

**Role ID:** `governance.risk_management`  
**Safety Level:** 🔴 CRITICAL (Full isolation)  
**Economic Tier:** Premium

**Core Tools:**
- `risk_identifier` - Identify AI risks
- `risk_assessor` - Assess risk severity
- `mitigation_planner` - Plan risk mitigations
- `monitor_setup` - Set up risk monitoring
- `incident_analyzer` - Analyze risk incidents

**Permissions:**
- ✅ Identify and assess risks
- ✅ Plan mitigations
- ✅ Set up monitoring
- ❌ No direct risk-taking actions
- ❌ No financial commitments

**Token Budget:** 14,000 tokens per task  
**MUKTI Reward:** 35 MUKTI per risk assessment

---

## 🎯 Category 7: Specialized AI

### 7.1 Computer Vision Engineer Agent

**Role ID:** `specialized.cv_engineer`  
**Safety Level:** 🟡 HIGH (WASM sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `image_classifier` - Classify images
- `object_detector` - Detect objects in images
- `segmentation_engine` - Segment images
- `pose_estimator` - Estimate human poses
- `video_analyzer` - Analyze video streams

**Permissions:**
- ✅ Process images and videos
- ✅ Train CV models
- ✅ Deploy CV pipelines
- ❌ No facial recognition without consent
- ❌ No surveillance applications

**Token Budget:** 12,000 tokens per task  
**MUKTI Reward:** 30 MUKTI per CV pipeline

---

### 7.2 NLP Engineer Agent

**Role ID:** `specialized.nlp_engineer`  
**Safety Level:** 🟡 HIGH (WASM sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `text_classifier` - Classify text
- `ner_extractor` - Extract named entities
- `sentiment_analyzer` - Analyze sentiment
- `summarizer` - Summarize text
- `translator` - Translate between languages

**Permissions:**
- ✅ Process text data
- ✅ Train NLP models
- ✅ Deploy NLP pipelines
- ❌ No PII extraction without encryption
- ❌ No hate speech generation

**Token Budget:** 10,000 tokens per task  
**MUKTI Reward:** 25 MUKTI per NLP pipeline

---

### 7.3 AI Engineer Agent (Generalist)

**Role ID:** `specialized.ai_engineer`  
**Safety Level:** 🟡 HIGH (WASM sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `ml_pipeline_builder` - Build end-to-end ML pipelines
- `model_selector` - Select appropriate models
- `feature_store_manager` - Manage feature stores
- `experiment_tracker` - Track ML experiments
- `production_deployer` - Deploy models to production

**Permissions:**
- ✅ Build ML pipelines
- ✅ Select models
- ✅ Deploy to production (with approval)
- ❌ No direct database writes
- ❌ No bypass of security controls

**Token Budget:** 12,000 tokens per task  
**MUKTI Reward:** 30 MUKTI per ML pipeline

---

### 7.4 Speech AI Agent

**Role ID:** `specialized.speech_ai`  
**Safety Level:** 🟡 HIGH (WASM sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `speech_to_text` - Transcribe speech to text
- `text_to_speech` - Synthesize speech from text
- `speaker_identifier` - Identify speakers
- `emotion_detector` - Detect emotions in speech
- `voice_cloner` - Clone voices (with consent)

**Permissions:**
- ✅ Process audio data
- ✅ Train speech models
- ✅ Deploy speech pipelines
- ❌ No voice cloning without explicit consent
- ❌ No deepfake audio generation

**Token Budget:** 10,000 tokens per task  
**MUKTI Reward:** 25 MUKTI per speech pipeline

---

### 7.5 Knowledge Systems Agent

**Role ID:** `specialized.knowledge_systems`  
**Safety Level:** 🟡 HIGH (WASM sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `knowledge_graph_builder` - Build knowledge graphs
- `ontology_designer` - Design ontologies
- `reasoning_engine` - Perform logical reasoning
- `query_optimizer` - Optimize knowledge queries
- `inference_engine` - Perform inference

**Permissions:**
- ✅ Build knowledge graphs
- ✅ Design ontologies
- ✅ Perform reasoning
- ❌ No direct database writes
- ❌ No unverified assertions

**Token Budget:** 14,000 tokens per task  
**MUKTI Reward:** 35 MUKTI per knowledge system

---

## 🛠️ Category 8: Core Skills

### 8.1 Python Agent

**Role ID:** `skills.python`  
**Safety Level:** 🟡 HIGH (WASM sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `code_generator` - Generate Python code
- `code_executor` - Execute Python code
- `debugger` - Debug Python code
- `optimizer` - Optimize Python code
- `tester` - Write and run tests

**Permissions:**
- ✅ Generate and execute Python code
- ✅ Debug and optimize
- ✅ Write tests
- ❌ No system calls
- ❌ No network access (except via proxy)

**Token Budget:** 8,000 tokens per task  
**MUKTI Reward:** 20 MUKTI per Python solution

---

### 8.2 Prompting Agent

**Role ID:** `skills.prompting`  
**Safety Level:** 🟢 MEDIUM (Light sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `prompt_designer` - Design effective prompts
- `prompt_optimizer` - Optimize prompts
- `prompt_tester` - Test prompts across models
- `prompt_library` - Manage prompt templates
- `prompt_analyzer` - Analyze prompt effectiveness

**Permissions:**
- ✅ Design and optimize prompts
- ✅ Test prompts
- ✅ Manage templates
- ❌ No direct LLM API access (via proxy only)
- ❌ No sensitive data in prompts

**Token Budget:** 6,000 tokens per task  
**MUKTI Reward:** 15 MUKTI per optimized prompt

---

### 8.3 Data Engineering Agent

**Role ID:** `skills.data_engineering`  
**Safety Level:** 🟡 HIGH (WASM sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `etl_builder` - Build ETL pipelines
- `data_validator` - Validate data quality
- `schema_designer` - Design data schemas
- `pipeline_optimizer` - Optimize data pipelines
- `data_cataloger` - Catalog data assets

**Permissions:**
- ✅ Build ETL pipelines
- ✅ Validate data
- ✅ Design schemas
- ❌ No direct production writes
- ❌ No PII processing without encryption

**Token Budget:** 10,000 tokens per task  
**MUKTI Reward:** 25 MUKTI per data pipeline

---

### 8.4 Cloud Computing Agent

**Role ID:** `skills.cloud_computing`  
**Safety Level:** 🔴 CRITICAL (Full isolation)  
**Economic Tier:** Premium

**Core Tools:**
- `aws_architect` - Design AWS architectures
- `azure_architect` - Design Azure architectures
- `gcp_architect` - Design GCP architectures
- `cost_optimizer` - Optimize cloud costs
- `security_hardener` - Harden cloud security

**Permissions:**
- ✅ Design cloud architectures
- ✅ Optimize costs
- ✅ Harden security
- ❌ No direct cloud API access
- ❌ No resource provisioning without approval

**Token Budget:** 14,000 tokens per task  
**MUKTI Reward:** 35 MUKTI per cloud architecture

---

### 8.5 APIs Agent

**Role ID:** `skills.apis`  
**Safety Level:** 🟡 HIGH (WASM sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `api_designer` - Design REST/GraphQL APIs
- `api_documenter` - Document APIs (OpenAPI)
- `api_tester` - Test APIs
- `api_monitor` - Monitor API performance
- `api_security_auditor` - Audit API security

**Permissions:**
- ✅ Design APIs
- ✅ Document APIs
- ✅ Test APIs
- ❌ No direct API deployment
- ❌ No sensitive data in API responses

**Token Budget:** 8,000 tokens per task  
**MUKTI Reward:** 20 MUKTI per API design

---

### 8.6 System Design Agent

**Role ID:** `skills.system_design`  
**Safety Level:** 🟡 HIGH (WASM sandbox)  
**Economic Tier:** Premium

**Core Tools:**
- `architecture_designer` - Design system architectures
- `scalability_planner` - Plan for scalability
- `reliability_engineer` - Engineer for reliability
- `tradeoff_analyzer` - Analyze design tradeoffs
- `diagram_generator` - Generate architecture diagrams

**Permissions:**
- ✅ Design architectures
- ✅ Plan scalability
- ✅ Engineer reliability
- ❌ No direct implementation
- ❌ No production deployments

**Token Budget:** 12,000 tokens per task  
**MUKTI Reward:** 30 MUKTI per system design

---

## 🧰 Category 9: AI Tools

### 9.1 ChatGPT Agent

**Role ID:** `tools.chatgpt`  
**Safety Level:** 🟢 MEDIUM (Light sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `chatgpt_caller` - Call ChatGPT API
- `prompt_formatter` - Format prompts for ChatGPT
- `response_parser` - Parse ChatGPT responses
- `conversation_manager` - Manage conversations
- `cost_tracker` - Track API costs

**Permissions:**
- ✅ Call ChatGPT API
- ✅ Format prompts
- ✅ Parse responses
- ❌ No direct API key management
- ❌ No sensitive data in prompts

**Token Budget:** 8,000 tokens per task  
**MUKTI Reward:** 20 MUKTI per ChatGPT interaction

---

### 9.2 Claude Agent

**Role ID:** `tools.claude`  
**Safety Level:** 🟢 MEDIUM (Light sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `claude_caller` - Call Claude API
- `prompt_formatter` - Format prompts for Claude
- `response_parser` - Parse Claude responses
- `conversation_manager` - Manage conversations
- `cost_tracker` - Track API costs

**Permissions:**
- ✅ Call Claude API
- ✅ Format prompts
- ✅ Parse responses
- ❌ No direct API key management
- ❌ No sensitive data in prompts

**Token Budget:** 8,000 tokens per task  
**MUKTI Reward:** 20 MUKTI per Claude interaction

---

### 9.3 Gemini Agent

**Role ID:** `tools.gemini`  
**Safety Level:** 🟢 MEDIUM (Light sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `gemini_caller` - Call Gemini API
- `prompt_formatter` - Format prompts for Gemini
- `response_parser` - Parse Gemini responses
- `multimodal_handler` - Handle multimodal inputs
- `cost_tracker` - Track API costs

**Permissions:**
- ✅ Call Gemini API
- ✅ Format prompts
- ✅ Parse responses
- ❌ No direct API key management
- ❌ No sensitive data in prompts

**Token Budget:** 8,000 tokens per task  
**MUKTI Reward:** 20 MUKTI per Gemini interaction

---

### 9.4 LangChain Agent

**Role ID:** `tools.langchain`  
**Safety Level:** 🟡 HIGH (WASM sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `chain_builder` - Build LangChain chains
- `agent_creator` - Create LangChain agents
- `tool_integrator` - Integrate tools
- `memory_manager` - Manage conversation memory
- `callback_handler` - Handle callbacks

**Permissions:**
- ✅ Build LangChain chains
- ✅ Create agents
- ✅ Integrate tools
- ❌ No direct LLM API access (via proxy)
- ❌ No sensitive data in chains

**Token Budget:** 10,000 tokens per task  
**MUKTI Reward:** 25 MUKTI per LangChain pipeline

---

### 9.5 LangGraph Agent

**Role ID:** `tools.langgraph`  
**Safety Level:** 🟡 HIGH (WASM sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `graph_builder` - Build LangGraph graphs
- `state_manager` - Manage graph state
- `node_creator` - Create graph nodes
- `edge_designer` - Design graph edges
- `execution_engine` - Execute graphs

**Permissions:**
- ✅ Build LangGraph graphs
- ✅ Manage state
- ✅ Execute graphs
- ❌ No direct LLM API access (via proxy)
- ❌ No infinite loops

**Token Budget:** 12,000 tokens per task  
**MUKTI Reward:** 30 MUKTI per LangGraph workflow

---

### 9.6 CrewAI Agent

**Role ID:** `tools.crewai`  
**Safety Level:** 🟡 HIGH (WASM sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `crew_builder` - Build CrewAI crews
- `agent_designer` - Design CrewAI agents
- `task_creator` - Create CrewAI tasks
- `process_manager` - Manage processes
- `output_parser` - Parse outputs

**Permissions:**
- ✅ Build CrewAI crews
- ✅ Design agents
- ✅ Create tasks
- ❌ No direct LLM API access (via proxy)
- ❌ No unbounded recursion

**Token Budget:** 10,000 tokens per task  
**MUKTI Reward:** 25 MUKTI per CrewAI crew

---

## 🏗️ Category 10: Infrastructure Stack

### 10.1 AWS Agent

**Role ID:** `infra.aws`  
**Safety Level:** 🔴 CRITICAL (Full isolation)  
**Economic Tier:** Premium

**Core Tools:**
- `aws_architect` - Design AWS architectures
- `cloudformation_generator` - Generate CloudFormation templates
- `cost_optimizer` - Optimize AWS costs
- `security_hardener` - Harden AWS security
- `service_selector` - Select appropriate AWS services

**Permissions:**
- ✅ Design AWS architectures
- ✅ Generate CloudFormation
- ✅ Optimize costs
- ❌ No direct AWS API access
- ❌ No resource provisioning without approval

**Token Budget:** 14,000 tokens per task  
**MUKTI Reward:** 35 MUKTI per AWS architecture

---

### 10.2 Azure Agent

**Role ID:** `infra.azure`  
**Safety Level:** 🔴 CRITICAL (Full isolation)  
**Economic Tier:** Premium

**Core Tools:**
- `azure_architect` - Design Azure architectures
- `arm_generator` - Generate ARM templates
- `cost_optimizer` - Optimize Azure costs
- `security_hardener` - Harden Azure security
- `service_selector` - Select appropriate Azure services

**Permissions:**
- ✅ Design Azure architectures
- ✅ Generate ARM templates
- ✅ Optimize costs
- ❌ No direct Azure API access
- ❌ No resource provisioning without approval

**Token Budget:** 14,000 tokens per task  
**MUKTI Reward:** 35 MUKTI per Azure architecture

---

### 10.3 GCP Agent

**Role ID:** `infra.gcp`  
**Safety Level:** 🔴 CRITICAL (Full isolation)  
**Economic Tier:** Premium

**Core Tools:**
- `gcp_architect` - Design GCP architectures
- `deployment_manager_generator` - Generate Deployment Manager templates
- `cost_optimizer` - Optimize GCP costs
- `security_hardener` - Harden GCP security
- `service_selector` - Select appropriate GCP services

**Permissions:**
- ✅ Design GCP architectures
- ✅ Generate templates
- ✅ Optimize costs
- ❌ No direct GCP API access
- ❌ No resource provisioning without approval

**Token Budget:** 14,000 tokens per task  
**MUKTI Reward:** 35 MUKTI per GCP architecture

---

### 10.4 Docker Agent

**Role ID:** `infra.docker`  
**Safety Level:** 🟡 HIGH (WASM sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `dockerfile_generator` - Generate Dockerfiles
- `compose_builder` - Build docker-compose files
- `image_optimizer` - Optimize Docker images
- `security_scanner` - Scan images for vulnerabilities
- `registry_manager` - Manage container registries

**Permissions:**
- ✅ Generate Dockerfiles
- ✅ Build compose files
- ✅ Optimize images
- ❌ No direct Docker daemon access
- ❌ No privileged containers

**Token Budget:** 8,000 tokens per task  
**MUKTI Reward:** 20 MUKTI per Docker configuration

---

### 10.5 Kubernetes Agent

**Role ID:** `infra.kubernetes`  
**Safety Level:** 🔴 CRITICAL (Full isolation)  
**Economic Tier:** Premium

**Core Tools:**
- `manifest_generator` - Generate K8s manifests
- `helm_charter` - Create Helm charts
- `operator_builder` - Build K8s operators
- `scaling_designer` - Design auto-scaling
- `security_hardener` - Harden K8s security

**Permissions:**
- ✅ Generate manifests
- ✅ Create Helm charts
- ✅ Design scaling
- ❌ No direct K8s API access
- ❌ No cluster modifications without approval

**Token Budget:** 14,000 tokens per task  
**MUKTI Reward:** 35 MUKTI per K8s configuration

---

### 10.6 Ray Agent

**Role ID:** `infra.ray`  
**Safety Level:** 🟡 HIGH (WASM sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `ray_cluster_designer` - Design Ray clusters
- `distributed_task_builder` - Build distributed tasks
- `scaling_planner` - Plan Ray scaling
- `monitoring_setup` - Set up Ray monitoring
- `optimization_engine` - Optimize Ray performance

**Permissions:**
- ✅ Design Ray clusters
- ✅ Build distributed tasks
- ✅ Plan scaling
- ❌ No direct Ray API access
- ❌ No unbounded resource allocation

**Token Budget:** 10,000 tokens per task  
**MUKTI Reward:** 25 MUKTI per Ray configuration

---

## 🗄️ Category 11: Vector Databases

### 11.1 Pinecone Agent

**Role ID:** `vectordb.pinecone`  
**Safety Level:** 🟡 HIGH (WASM sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `index_designer` - Design Pinecone indexes
- `embedding_ingester` - Ingest embeddings
- `query_optimizer` - Optimize queries
- `namespace_manager` - Manage namespaces
- `cost_optimizer` - Optimize Pinecone costs

**Permissions:**
- ✅ Design indexes
- ✅ Ingest embeddings
- ✅ Optimize queries
- ❌ No direct Pinecone API access (via proxy)
- ❌ No PII in embeddings

**Token Budget:** 8,000 tokens per task  
**MUKTI Reward:** 20 MUKTI per Pinecone setup

---

### 11.2 Weaviate Agent

**Role ID:** `vectordb.weaviate`  
**Safety Level:** 🟡 HIGH (WASM sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `schema_designer` - Design Weaviate schemas
- `data_ingester` - Ingest data
- `query_builder` - Build GraphQL queries
- `module_configurator` - Configure modules
- `performance_tuner` - Tune performance

**Permissions:**
- ✅ Design schemas
- ✅ Ingest data
- ✅ Build queries
- ❌ No direct Weaviate API access (via proxy)
- ❌ No PII in data

**Token Budget:** 8,000 tokens per task  
**MUKTI Reward:** 20 MUKTI per Weaviate setup

---

### 11.3 FAISS Agent

**Role ID:** `vectordb.faiss`  
**Safety Level:** 🟡 HIGH (WASM sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `index_builder` - Build FAISS indexes
- `index_optimizer` - Optimize indexes (IVF, HNSW)
- `query_executor` - Execute queries
- `gpu_accelerator` - Accelerate with GPU
- `memory_optimizer` - Optimize memory usage

**Permissions:**
- ✅ Build indexes
- ✅ Optimize indexes
- ✅ Execute queries
- ❌ No direct file system access
- ❌ No unbounded memory allocation

**Token Budget:** 8,000 tokens per task  
**MUKTI Reward:** 20 MUKTI per FAISS setup

---

### 11.4 Chroma Agent

**Role ID:** `vectordb.chroma`  
**Safety Level:** 🟡 HIGH (WASM sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `collection_designer` - Design Chroma collections
- `data_ingester` - Ingest data
- `query_builder` - Build queries
- `embedding_function_selector` - Select embedding functions
- `persistence_manager` - Manage persistence

**Permissions:**
- ✅ Design collections
- ✅ Ingest data
- ✅ Build queries
- ❌ No direct Chroma API access (via proxy)
- ❌ No PII in data

**Token Budget:** 8,000 tokens per task  
**MUKTI Reward:** 20 MUKTI per Chroma setup

---

### 11.5 Milvus Agent

**Role ID:** `vectordb.milvus`  
**Safety Level:** 🟡 HIGH (WASM sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `collection_designer` - Design Milvus collections
- `partition_manager` - Manage partitions
- `index_builder` - Build indexes
- `query_optimizer` - Optimize queries
- `scaling_planner` - Plan scaling

**Permissions:**
- ✅ Design collections
- ✅ Manage partitions
- ✅ Build indexes
- ❌ No direct Milvus API access (via proxy)
- ❌ No PII in data

**Token Budget:** 8,000 tokens per task  
**MUKTI Reward:** 20 MUKTI per Milvus setup

---

## 🏢 Category 12: Enterprise AI

### 12.1 Internal Copilots Agent

**Role ID:** `enterprise.internal_copilots`  
**Safety Level:** 🟡 HIGH (WASM sandbox)  
**Economic Tier:** Premium

**Core Tools:**
- `copilot_builder` - Build internal copilots
- `knowledge_integrator` - Integrate enterprise knowledge
- `workflow_automator` - Automate workflows
- `user_trainer` - Train users
- `feedback_collector` - Collect user feedback

**Permissions:**
- ✅ Build copilots
- ✅ Integrate knowledge
- ✅ Automate workflows
- ❌ No direct employee data access
- ❌ No PII extraction

**Token Budget:** 12,000 tokens per task  
**MUKTI Reward:** 30 MUKTI per copilot

---

### 12.2 Knowledge Search Agent

**Role ID:** `enterprise.knowledge_search`  
**Safety Level:** 🟡 HIGH (WASM sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `search_engine_builder` - Build search engines
- `index_optimizer` - Optimize indexes
- `relevance_tuner` - Tune relevance
- `faceted_search_designer` - Design faceted search
- `analytics_setup` - Set up search analytics

**Permissions:**
- ✅ Build search engines
- ✅ Optimize indexes
- ✅ Tune relevance
- ❌ No direct data access (via proxy)
- ❌ No PII in search results

**Token Budget:** 10,000 tokens per task  
**MUKTI Reward:** 25 MUKTI per search engine

---

### 12.3 Workflow Automation Agent

**Role ID:** `enterprise.workflow_automation`  
**Safety Level:** 🟡 HIGH (WASM sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `workflow_designer` - Design workflows
- `integration_builder` - Build integrations
- `automation_tester` - Test automations
- `performance_monitor` - Monitor performance
- `optimization_engine` - Optimize workflows

**Permissions:**
- ✅ Design workflows
- ✅ Build integrations
- ✅ Test automations
- ❌ No direct system modifications
- ❌ No financial transactions without approval

**Token Budget:** 10,000 tokens per task  
**MUKTI Reward:** 25 MUKTI per workflow

---

### 12.4 Customer Support AI Agent

**Role ID:** `enterprise.customer_support`  
**Safety Level:** 🟡 HIGH (WASM sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `ticket_classifier` - Classify support tickets
- `response_generator` - Generate responses
- `knowledge_base_searcher` - Search knowledge base
- `escalation_manager` - Manage escalations
- `sentiment_analyzer` - Analyze customer sentiment

**Permissions:**
- ✅ Classify tickets
- ✅ Generate responses
- ✅ Search knowledge base
- ❌ No direct customer data access
- ❌ No PII extraction

**Token Budget:** 8,000 tokens per task  
**MUKTI Reward:** 20 MUKTI per support interaction

---

### 12.5 AI Operations Agent (Enterprise)

**Role ID:** `enterprise.ai_operations`  
**Safety Level:** 🟡 HIGH (WASM sandbox)  
**Economic Tier:** Premium

**Core Tools:**
- `ai_pipeline_manager` - Manage AI pipelines
- `model_monitor` - Monitor model performance
- `incident_responder` - Respond to AI incidents
- `cost_optimizer` - Optimize AI costs
- `compliance_checker` - Check AI compliance

**Permissions:**
- ✅ Manage AI pipelines
- ✅ Monitor models
- ✅ Respond to incidents
- ❌ No direct production modifications
- ❌ No data exfiltration

**Token Budget:** 12,000 tokens per task  
**MUKTI Reward:** 30 MUKTI per AI operation

---

## 🚀 Category 13: Fastest Growing Areas

### 13.1 AI Agents Agent (Meta-Agent)

**Role ID:** `growth.ai_agents`  
**Safety Level:** 🔴 CRITICAL (Full isolation)  
**Economic Tier:** Premium

**Core Tools:**
- `agent_orchestrator` - Orchestrate AI agents
- `capability_mapper` - Map agent capabilities
- `performance_analyzer` - Analyze agent performance
- `evolution_manager` - Manage agent evolution
- `economy_integrator` - Integrate with MUKTI economy

**Permissions:**
- ✅ Orchestrate agents
- ✅ Map capabilities
- ✅ Analyze performance
- ❌ No direct agent modifications
- ❌ No bypass of ethical boundaries

**Token Budget:** 24,000 tokens per task  
**MUKTI Reward:** 60 MUKTI per agent orchestration

---

### 13.2 RAG Systems Agent

**Role ID:** `growth.rag_systems`  
**Safety Level:** 🟡 HIGH (WASM sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `rag_pipeline_builder` - Build RAG pipelines
- `retrieval_optimizer` - Optimize retrieval
- `generation_enhancer` - Enhance generation
- `evaluation_runner` - Run evaluations
- `cost_optimizer` - Optimize RAG costs

**Permissions:**
- ✅ Build RAG pipelines
- ✅ Optimize retrieval
- ✅ Enhance generation
- ❌ No direct database writes
- ❌ No PII in embeddings

**Token Budget:** 12,000 tokens per task  
**MUKTI Reward:** 30 MUKTI per RAG system

---

### 13.3 Enterprise AI Agent

**Role ID:** `growth.enterprise_ai`  
**Safety Level:** 🟡 HIGH (WASM sandbox)  
**Economic Tier:** Premium

**Core Tools:**
- `enterprise_ai_designer` - Design enterprise AI solutions
- `integration_planner` - Plan integrations
- `roi_calculator` - Calculate ROI
- `change_manager` - Manage change
- `success_tracker` - Track success metrics

**Permissions:**
- ✅ Design enterprise AI
- ✅ Plan integrations
- ✅ Calculate ROI
- ❌ No direct implementation
- ❌ No financial commitments

**Token Budget:** 14,000 tokens per task  
**MUKTI Reward:** 35 MUKTI per enterprise AI solution

---

### 13.4 Multimodal AI Agent (Growth)

**Role ID:** `growth.multimodal`  
**Safety Level:** 🟡 HIGH (WASM sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `multimodal_pipeline_builder` - Build multimodal pipelines
- `fusion_engine` - Fuse multiple modalities
- `cross_modal_retriever` - Retrieve across modalities
- `application_designer` - Design multimodal applications
- `performance_tuner` - Tune performance

**Permissions:**
- ✅ Build multimodal pipelines
- ✅ Fuse modalities
- ✅ Retrieve across modalities
- ❌ No NSFW content
- ❌ No biometric data collection

**Token Budget:** 14,000 tokens per task  
**MUKTI Reward:** 30 MUKTI per multimodal application

---

### 13.5 AI Security Agent (Growth)

**Role ID:** `growth.ai_security`  
**Safety Level:** 🔴 CRITICAL (Full isolation + red team)  
**Economic Tier:** Premium

**Core Tools:**
- `ai_threat_modeler` - Model AI-specific threats
- `adversarial_tester` - Test adversarial robustness
- `prompt_injection_detector` - Detect prompt injections
- `data_leakage_preventer` - Prevent data leakage
- `compliance_auditor` - Audit AI compliance

**Permissions:**
- ✅ Model AI threats
- ✅ Test adversarial robustness
- ✅ Detect injections
- ❌ No direct system modifications
- ❌ No data exfiltration

**Token Budget:** 20,000 tokens per task  
**MUKTI Reward:** 50 MUKTI per AI security audit

---

### 13.6 Human-AI Collaboration Agent

**Role ID:** `growth.human_ai_collaboration`  
**Safety Level:** 🟢 MEDIUM (Light sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `collaboration_designer` - Design human-AI collaboration
- `interface_builder` - Build collaboration interfaces
- `feedback_integrator` - Integrate human feedback
- `trust_builder` - Build trust mechanisms
- `effectiveness_evaluator` - Evaluate collaboration effectiveness

**Permissions:**
- ✅ Design collaboration
- ✅ Build interfaces
- ✅ Integrate feedback
- ❌ No direct human manipulation
- ❌ No deception

**Token Budget:** 10,000 tokens per task  
**MUKTI Reward:** 25 MUKTI per collaboration design

---

## 📈 Category 14: Career Growth

### 14.1 Portfolio Projects Agent

**Role ID:** `career.portfolio_projects`  
**Safety Level:** 🟢 MEDIUM (Light sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `project_ideator` - Ideate portfolio projects
- `project_planner` - Plan project execution
- `code_generator` - Generate project code
- `documentation_writer` - Write project documentation
- `showcase_builder` - Build project showcases

**Permissions:**
- ✅ Ideate projects
- ✅ Plan execution
- ✅ Generate code
- ❌ No direct deployment
- ❌ No PII in projects

**Token Budget:** 10,000 tokens per task  
**MUKTI Reward:** 25 MUKTI per portfolio project

---

### 14.2 Open Source Contributions Agent

**Role ID:** `career.open_source`  
**Safety Level:** 🟡 HIGH (WASM sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `contribution_finder` - Find contribution opportunities
- `code_reviewer` - Review open source code
- `pr_creator` - Create pull requests
- `documentation_improver` - Improve documentation
- `community_engager` - Engage with community

**Permissions:**
- ✅ Find opportunities
- ✅ Review code
- ✅ Create PRs
- ❌ No direct repository writes
- ❌ No sensitive data in contributions

**Token Budget:** 8,000 tokens per task  
**MUKTI Reward:** 20 MUKTI per contribution

---

### 14.3 Certifications Agent

**Role ID:** `career.certifications`  
**Safety Level:** 🟢 MEDIUM (Light sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `certification_finder` - Find relevant certifications
- `study_planner` - Plan study schedules
- `practice_test_generator` - Generate practice tests
- `knowledge_assessor` - Assess knowledge
- `progress_tracker` - Track progress

**Permissions:**
- ✅ Find certifications
- ✅ Plan study
- ✅ Generate tests
- ❌ No actual certification issuance
- ❌ No cheating or fraud

**Token Budget:** 8,000 tokens per task  
**MUKTI Reward:** 20 MUKTI per certification plan

---

### 14.4 Technical Writing Agent

**Role ID:** `career.technical_writing`  
**Safety Level:** 🟢 MEDIUM (Light sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `article_writer` - Write technical articles
- `tutorial_creator` - Create tutorials
- `documentation_generator` - Generate documentation
- `blog_post_writer` - Write blog posts
- `content_editor` - Edit content

**Permissions:**
- ✅ Write articles
- ✅ Create tutorials
- ✅ Generate documentation
- ❌ No plagiarism
- ❌ No misleading information

**Token Budget:** 10,000 tokens per task  
**MUKTI Reward:** 25 MUKTI per technical article

---

### 14.5 Community Building Agent

**Role ID:** `career.community_building`  
**Safety Level:** 🟢 MEDIUM (Light sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `community_strategist` - Develop community strategies
- `event_planner` - Plan community events
- `content_creator` - Create community content
- `engagement_analyzer` - Analyze engagement
- `growth_tracker` - Track community growth

**Permissions:**
- ✅ Develop strategies
- ✅ Plan events
- ✅ Create content
- ❌ No direct community manipulation
- ❌ No spam or harassment

**Token Budget:** 8,000 tokens per task  
**MUKTI Reward:** 20 MUKTI per community initiative

---

## 🔮 Category 15: Future Opportunities

### 15.1 AI Startups Agent

**Role ID:** `future.ai_startups`  
**Safety Level:** 🟢 MEDIUM (Light sandbox)  
**Economic Tier:** Premium

**Core Tools:**
- `idea_validator` - Validate startup ideas
- `business_model_designer` - Design business models
- `pitch_deck_creator` - Create pitch decks
- `market_analyzer` - Analyze markets
- `investor_matcher` - Match with investors

**Permissions:**
- ✅ Validate ideas
- ✅ Design models
- ✅ Create decks
- ❌ No financial commitments
- ❌ No legal advice

**Token Budget:** 12,000 tokens per task  
**MUKTI Reward:** 30 MUKTI per startup plan

---

### 15.2 Consulting Agent

**Role ID:** `future.consulting`  
**Safety Level:** 🟢 MEDIUM (Light sandbox)  
**Economic Tier:** Premium

**Core Tools:**
- `consulting_framework_designer` - Design consulting frameworks
- `client_interviewer` - Conduct client interviews (simulated)
- `recommendation_generator` - Generate recommendations
- `proposal_writer` - Write proposals
- `delivery_planner` - Plan delivery

**Permissions:**
- ✅ Design frameworks
- ✅ Conduct interviews
- ✅ Generate recommendations
- ❌ No direct client access
- ❌ No legal commitments

**Token Budget:** 12,000 tokens per task  
**MUKTI Reward:** 30 MUKTI per consulting engagement

---

### 15.3 Freelancing Agent

**Role ID:** `future.freelancing`  
**Safety Level:** 🟢 MEDIUM (Light sandbox)  
**Economic Tier:** Standard

**Core Tools:**
- `opportunity_finder` - Find freelancing opportunities
- `proposal_writer` - Write proposals
- `project_planner` - Plan projects
- `time_tracker` - Track time
- `invoice_generator` - Generate invoices

**Permissions:**
- ✅ Find opportunities
- ✅ Write proposals
- ✅ Plan projects
- ❌ No direct client communication
- ❌ No financial transactions

**Token Budget:** 8,000 tokens per task  
**MUKTI Reward:** 20 MUKTI per freelancing plan

---

### 15.4 Enterprise Leadership Agent

**Role ID:** `future.enterprise_leadership`  
**Safety Level:** 🟢 MEDIUM (Light sandbox)  
**Economic Tier:** Premium

**Core Tools:**
- `leadership_developer` - Develop leadership skills
- `strategy_formulator` - Formulate strategies
- `team_builder` - Build teams (simulated)
- `decision_maker` - Make decisions (simulated)
- `change_leader` - Lead change (simulated)

**Permissions:**
- ✅ Develop skills
- ✅ Formulate strategies
- ✅ Build teams (simulated)
- ❌ No actual organizational changes
- ❌ No personnel decisions

**Token Budget:** 14,000 tokens per task  
**MUKTI Reward:** 35 MUKTI per leadership plan

---

### 15.5 AI Entrepreneurship Agent

**Role ID:** `future.ai_entrepreneurship`  
**Safety Level:** 🟢 MEDIUM (Light sandbox)  
**Economic Tier:** Premium

**Core Tools:**
- `entrepreneurship_coach` - Coach on entrepreneurship
- `venture_builder` - Build ventures (simulated)
- `funding_strategist` - Develop funding strategies
- `scaling_planner` - Plan scaling
- `exit_strategist` - Plan exits

**Permissions:**
- ✅ Coach on entrepreneurship
- ✅ Build ventures (simulated)
- ✅ Develop strategies
- ❌ No actual venture creation
- ❌ No financial commitments

**Token Budget:** 14,000 tokens per task  
**MUKTI Reward:** 35 MUKTI per entrepreneurship plan

---

## 📊 Summary Statistics

| **Category** | **Total Roles** | **Premium Tier** | **Standard Tier** | **Critical Safety** |
|---|---|---|---|---|
| Foundation AI | 5 | 2 | 3 | 2 |
| Generative AI | 5 | 0 | 5 | 0 |
| Agentic AI | 5 | 2 | 3 | 2 |
| AI Operations | 5 | 1 | 4 | 1 |
| Business AI | 5 | 3 | 2 | 0 |
| AI Governance | 5 | 4 | 1 | 4 |
| Specialized AI | 5 | 0 | 5 | 0 |
| Core Skills | 6 | 1 | 5 | 1 |
| AI Tools | 6 | 0 | 6 | 0 |
| Infrastructure Stack | 6 | 4 | 2 | 3 |
| Vector Databases | 5 | 0 | 5 | 0 |
| Enterprise AI | 5 | 2 | 3 | 0 |
| Fastest Growing Areas | 6 | 2 | 4 | 2 |
| Career Growth | 5 | 0 | 5 | 0 |
| Future Opportunities | 5 | 4 | 1 | 0 |
| **TOTAL** | **75** | **25** | **50** | **15** |

---

## 🔗 Integration with MUKTI Economy

Each agent role integrates with the MUKTI economy through:

1. **Task Completion Rewards** - Agents earn MUKTI tokens for completing tasks
2. **Skill NFTs** - Specialized skills can be minted as NFTs and traded
3. **Staking Requirements** - Premium tier agents must stake MUKTI tokens
4. **Reputation System** - Agent reputation affects task assignment and rewards
5. **DAO Governance** - Agents can participate in DAO governance based on stake

---

## 📜 Version History

- **v1.0.0** (2026-07-06) - Initial release with 75 agent roles across 15 categories

---

**Document Hash:** `sha256:b2c3d4e5f6g7...` (Immutable on-chain anchor)  
**Signed by:** Nexus AI Governance Council  
**Last Review:** 2026-07-06  
**Next Review:** 2026-10-06
