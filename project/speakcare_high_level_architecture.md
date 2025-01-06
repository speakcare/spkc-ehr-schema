# **SpeakCare System Architecture**

## **Overview**

SpeakCare is an ambient listening system for nurses that captures audio conversations, processes them, and generates structured clinical documentation ready for submission to Electronic Health Records (EHR) systems. 
The microphone escorts the nurse during the whole shift, and any conversation can potentially be used to create and improve documentation.  

The architecture ensures scalability, fault tolerance, and compliance with HIPAA.

---

## **1. System Components**

### **1.1 Frontend Application**
- **Type:** Browser Extension and Mobile Application.  
- **Purpose:** Enables nurses to interact with candidate documentation and receive notifications.  
- **Features:**
  - **Browser Extension**:  
     - View candidate documentation.  
     - Approve and submit documentation to EHR.
     - User feedback interface for real-time edits and corrections.
  - **Mobile App**:  
     - Notifications for flagged, incomplete, or pending documents.  
     - Task management and smart reminders.  
  - **Security**: OAuth 2.0 (3-legged authentication) for secure login.  
- **Technologies:**  
   - Browser: React.js/Vue.js with API integration.  
   - Mobile: Flutter/React Native for cross-platform support.

---

### **1.2 Orchestration and Workflow Management**
- **Type:** Workflow Engine.  
- **Purpose:** Orchestrates sequential execution of microservices in the data pipeline.  
- **Responsibilities:**  
   - Trigger and monitor:  
     - **Audio Ingestion → STT → Text Sanitization → Patient Attribution → Patient Data Sanitization → Sentiment Analysis → EHR Integration → Knowledge Base → Documentation Preparation → Rule-Based Processing → Compliance Framework**.  
   - Ensure retries, fault tolerance, and step recovery.  
- **Technologies:**  
   - Apache Airflow, Temporal, or Step Functions.

---

### **1.3 Audio Ingestion and Pre-Processing Service**
- **Type:** Microservice.  
- **Purpose:** Collects audio from mobile devices, enhances it, and prepares it for STT processing.  
- **Features:**
   - **Audio Enhancement**: Noise reduction, speech enhancement, echo cancellation, and normalization.  
   - **Segmentation**: Splits audio into manageable chunks with timestamps.  
   - **Speaker Recognition**: Build and update speaker profiles progressively for better attribution.  
   - **Sentiment Detection**: Detect critical cues such as distress, coughing, or shouting.  
   - **Metadata Tagging**: Adds timestamps, user ID, and device metadata.  
   - **Temporary Storage**: Enhanced audio is stored in an object store for downstream processing.  
- **Technologies:**  
   - Audio Processing: SoX, WebRTC Noise Reduction, PyDub.  
   - Storage: AWS S3-compatible object store.

---

### **1.4 Speech-to-Text (STT) Service**
- **Type:** Microservice.  
- **Purpose:** Converts pre-processed audio into text with speaker diarization.  
- **Features:**
   - Accepts audio from the Audio Enhancement Service.  
   - Performs speaker diarization to identify and label individual speakers.  
   - Outputs raw text with timestamps and speaker labels.  
- **Technologies:**  
   - Python with STT services like OpenAI Whisper, Google STT, or Azure Speech-to-Text.  
   - Deployment: Docker/Kubernetes for scalability.  

---

### **1.5 Initial Text Sanitization Service**
- **Type:** Microservice.  
- **Purpose:** Cleans irrelevant data from raw STT output before patient attribution.  
- **Features:**
   - Filters casual or irrelevant conversations (e.g., personal chats during breaks).  
   - Rule-based and ML-based filtering to identify and remove noise.  
   - Outputs sanitized text to the NoSQL Document Database for Patient Attribution.  
- **Technologies:**  
   - Python with NLP-based filtering pipelines.  
   - Deployment: Docker/Kubernetes for scalability.

---

### **1.6 Patient Attribution and Context Construction Service**
- **Type:** Microservice.  
- **Purpose:** Identifies the patient associated with conversations and reconstructs context streams for the patient.  
- **Features:**
   - Context Identification:
       - Uses keywords, phrases, and verbal cues (e.g., "Regarding [Patient Name]").  
       - Cross-references with the EHR to validate patient identity using conditions, medications, and other details.  
   - Segment Linking:
       - Merges snippets into coherent streams using rules or ML models.  
       - Applies time thresholds to group interactions (e.g., 10-15 minutes without explicit interruption).  
       - Uses semantic similarity analysis with transformer models (e.g., BERT) to link segments.  
- **Technologies:**  
   - Python with NLP libraries (SpaCy, Hugging Face Transformers).  

---

### **1.7 Patient Data Sanitization Service**
- **Type:** Microservice.  
- **Purpose:** Filters and sanitizes raw text to ensure relevance and compliance.  
- **Features:**
   - Rule-based and ML-based filtering.  
   - Removes irrelevant, private, or harmful information.  
   - Updates sanitized text back to the NoSQL Database.  
- **Technologies:**  
   - Python-based pipeline with rule-based sanitization.  

---

### **1.8 Sentiment Analysis Service**
- **Type:** Microservice.  
- **Purpose:** Detects emotional cues, complaints, and changes in patient conditions.  
- **Features:**
   - **Audio Sentiment Analysis**: Identify tone, distress, or critical audio cues (e.g., shouting, coughing).  
   - **Text Sentiment Analysis**: Extract complaints and pain descriptions from text.  
- **Technologies:**  
   - Python with pre-trained transformer models (e.g., BERT, OpenAI).

---

### **1.9 EHR Integration Service**
- **Type:** Microservice.  
- **Purpose:** Manages reading and writing data to the EHR.  
- **Features:**
   - **EHR Read Service**: Fetches patient history and metadata.  
   - **EHR Write Service**: Submits approved documentation to the EHR.  
   - Secure integration using OAuth 2.0 for authentication.  
- **Technologies:**  
   - Python with EHR APIs/SDKs.

---

### **1.10 Knowledge Base Management Service**
- **Type:** Microservice.  
- **Purpose:** Centralized storage and retrieval of knowledge for dynamic prompting and compliance.  
- **Features:**
   - **Knowledge Sources**: CMS protocols, ICD-10, organizational templates, nurse-specific styles, etc.  
   - **Vector Database**: Semantic search for embeddings (e.g., Pinecone).  
   - **Graph Database**: Store relational data (e.g., templates and conditions).  
- **Technologies:**  
   - Vector Database: Pinecone or FAISS.  
   - Graph Database: Neo4j.

---

### **1.11 Documentation Conversion Service (LLM)**
- **Type:** Microservice.  
- **Purpose:** Converts sanitized text and retrieved knowledge into structured clinical documentation.  
- **Features:**
   - Use LLM with dynamic prompting for structured notes generation.  
   - Integrates with Knowledge Base for dynamic templates, rules, and compliance information.  
   - Enforces JSON schema validation for structured outputs.  
- **Technologies:**  
   - OpenAI GPT API or equivalent LLM.  
   - JSON schema validation for output safety.  

---

### **1.12 Rule-Based Post-Processing**
- **Type:** Microservice.  
- **Purpose:** Ensures that LLM outputs are compliant, optimized, and aligned with various requirements before submission.  
- **Features:**
   - Apply rules for:
     - **HIPAA Compliance**: Ensure no Protected Health Information (PHI) or Personally Identifiable Information (PII) violations occur in output.  
     - **Clinical Compliance**: Adherence to CMS protocols and other regulatory standards.  
     - **Reimbursement Optimization**: Tailor documentation to maximize accuracy and completeness for billing and reimbursement models (e.g., PDPM, DRG, RUG-III).  
     - **Liability Mitigation**: Flag potentially harmful or legally sensitive statements.  
     - **Organization Policies**: Enforce specific documentation styles, templates, and terminologies defined by the organization.  
     - **Personal Style**: Align generated documentation with the preferred style and language of individual nurses.  
   - Modular design to enable tenant-specific rules.  
   - Validate outputs against documentation guidelines and regulatory standards.  
- **Technologies:**  
   - NLP libraries (spaCy) for rule implementation and validation.  
   - Custom rule-based systems for tenant-specific policies and templates.  

---

### **1.13 Smart Task Manager**
- **Type:** Microservice.  
- **Purpose:** Generate dynamic task lists and reminders for nurses.  
- **Features:**  
   - Fetch task schedules from EHR.  
   - Generate notifications for overdue or high-priority tasks.  

---

### **1.14 Compliance and Audit Framework**
- **Type:** Framework.  
- **Purpose:** Replace PII with placeholders and ensure audit logging.  
- **Features:**  
   - Detect and replace PII in free-text data.  
   - Maintain audit logs for compliance tracking.

---

### **1.15 Web Application Service**
- **Type:** Microservice.  
- **Purpose:** Centralized API gateway for managing system interactions.  
- **Features:**
   - Supports human-in-the-loop corrections for flagged or draft notes.  
   - Provides endpoints for frontend communication (browser/mobile).  
   - Handles authentication and session management.  
- **Technologies:**  
   - Django/Flask API framework.

---

### **1.16 Monitoring and Logging**
- **Purpose:** Provides real-time monitoring, logging, and HIPAA audit trails.  
- **Technologies:**  
   - DataDog, ELK Stack (Elasticsearch, Logstash, Kibana), or AWS CloudWatch.  

---

### **1.17 User Management**
- **Purpose:** Centralized authentication and authorization for all users.  
- **Features:**  
   - OAuth 2.0 for secure integration with EHR systems (e.g., PCC).  
   - Role-Based Access Control (RBAC) for internal and external users.  
- **Technologies:**  
   - AWS Cognito, Okta, or equivalent IDM solutions.  

---

### **1.18 Deployment Infrastructure**
- **Components:**
   - **Infrastructure as Code (IaC):** Terraform or CloudFormation.  
   - **Container Orchestration:** Kubernetes for scalable deployments.  
   - **CI/CD Pipelines:** Automated builds, tests, and security scans.  

---

### **1.19 Data Storage**
- **Components:**
   - **Object Store**: Temporary storage for audio and raw text.  
   - **NoSQL Document Database**: Stores intermediate text outputs (STT, Patient Attribution, Sanitized Text).  
   - **Relational Database (PostgreSQL)**: Holds candidate documents awaiting user approval.  
   - **Data Lake**: Archives processed data for analytics and future AI/ML pipelines.  

---

### **1.20 Human-in-the-Loop (HITL) Service**
- **Type:** Microservice.  
- **Purpose:** Allows human intervention in real-time to review, correct, and improve data at any stage of the pipeline.  
- **Features:**
   - **APIs for Intervention**:
       - Provides APIs via the Web Application Service for reviewing and altering data at various pipeline stages.
   - **Feedback Integration**:
       - Updates corrected data into relevant knowledge bases and workflows to improve system behavior over time.
   - **User Interfaces**:
       - **Nurse Frontend**: Integrated into the Nurse Frontend (Browser Extension or Mobile App) to allow simple corrections, such as updating patient attributions or refining documentation.
       - **Internal Application**: A dedicated application for the SpeakCare team to perform in-depth debugging, auditing, and compliance checks.
   - **Audit Logging**:
       - Tracks all human interventions to ensure regulatory compliance and traceability.  
   - **Multi-Tenant Support**:
       - Segregates HITL operations for different organizations and users to maintain data privacy and compliance.
---

### **1.21 Event Queue Management**
Ensure scalability, fault tolerance, and efficient data flow across all stages of the pipeline while providing the flexibility to support real-time and asynchronous workflows.

- **Type:** Messaging Infrastructure.  
- **Purpose:** Manages asynchronous communication and data flow between microservices in the data pipeline.  

- **Responsibilities:**  
   - **Event Publishing and Subscription**:  
     - Facilitate seamless data exchange between services by enabling producers to publish messages and consumers to subscribe to relevant topics or queues.  
   - **Decoupling Services**:  
     - Ensure microservices operate independently, reducing dependencies and enabling flexible scaling.  
   - **Message Durability and Replay**:  
     - Persist messages for configurable durations, allowing downstream services to replay events in case of failures or reprocessing needs.  
   - **Load Balancing and Backpressure Management**:  
     - Distribute workloads evenly across consumers and buffer messages to prevent overloading services.  
   - **Real-Time Event Streaming**:  
     - Enable real-time processing and event-driven workflows, ensuring data is immediately available to dependent services.  

- **Integration with Workflow Orchestration**:  
   - Complements the workflow engine by serving as the communication layer, allowing the orchestrator to trigger actions based on message-driven events.

- **Technologies:**  
   - Apache Kafka, RabbitMQ, or AWS SQS/SNS.  

- **Proposed Workflow Examples**:  
   - **Audio Ingestion**: Publishes enhanced audio events (e.g., `audio_ready` topic) for downstream processing.  
   - **STT Processing**: Subscribes to `audio_ready`, processes the data, and publishes results to `transcribed_text_ready`.  
   - **Sanitization**: Subscribes to `transcribed_text_ready` and publishes sanitized outputs to `sanitized_text_ready`.  
   - **Compliance Framework**: Consumes events from multiple stages for monitoring and audit logging.  

#### **Integration with Remaining Components**
The **Human-in-the-Loop Service** integrates seamlessly with the following components:
1. **Knowledge Base Management Service**:
   - Updates intervention feedback as new rules, templates, or personalized preferences in the Knowledge Base.
   - Example: A correction to a progress note style is added to a nurse's profile for future documentation generation.
2. **Rule-Based Post-Processing**:
   - Allows intervention to refine compliance rules or resolve flagged issues related to HIPAA, CMS protocols, liability, or organizational styles.
3. **Documentation Preparation Service (LLM)**:
   - Provides real-time feedback to enhance LLM outputs for structured clinical notes.
   - Example: Flagging misinterpreted data from the LLM for correction and reintegration.
4. **EHR Integration Service**:
   - Enables final corrections before document submission to the EHR, ensuring compliance and quality.
5. **Audit Framework**:
   - Logs interventions at every stage, including data transformations and final approvals, ensuring a complete audit trail.

---

## **2. Core System Flows**

### **2.1 Audio Ingestion to Text Flow**
1. **Mobile App → Audio Ingestion Service**:
   - Audio is collected, enhanced (noise reduction, echo cancellation), and segmented into chunks with timestamps.
   - Sentiment cues such as shouting or distress are detected at this stage.
2. **Audio Ingestion Service → STT Service**:
   - Enhanced audio is converted to text with diarization (speaker identification and labeling).
3. **STT Service → Initial Text Sanitization Service**:
   - Casual or irrelevant conversations (e.g., personal chats) are filtered out.
4. **Sanitized text → NoSQL Database**:
   - Outputs are stored for subsequent processing.

---

### **2.2 Data Processing Flow**
1. **Workflow Orchestrator triggers sequential services**:
   - **Patient Attribution and Context Construction**:
     - Identify the patient associated with the conversation and reconstruct their conversation streams.
   - **Human-in-the-Loop (HITL) Service** (Optional Intervention):
     - Review and refine patient attribution results as needed.
   - **Patient Data Sanitization**:
     - Remove irrelevant, private, or harmful information to ensure relevance and compliance.
   - **Sentiment Analysis**:
     - Analyze text for patient complaints, pain levels, and other indicators of emotional or physical distress.
   - **Human-in-the-Loop (HITL) Service** (Optional Intervention):
     - Review flagged sentiment analysis results and provide corrections if necessary.
   - **EHR Integration**:
     - Fetch relevant patient data (e.g., history, medication) to enrich processing.
   - **Knowledge Base Management**:
     - Retrieve templates, organizational rules, and nurse-specific styles for use in subsequent stages.
   - **Documentation Preparation (LLM)**:
     - Use the LLM to generate structured clinical documentation, enriched by the knowledge base.
   - **Human-in-the-Loop (HITL) Service** (Optional Intervention):
     - Review LLM-generated documentation, refine structured notes, or adjust outputs.
   - **Rule-Based Post-Processing**:
     - Validate generated outputs against rules for HIPAA compliance, CMS protocols, reimbursement optimization, liability, and organizational or personal styles.
2. **Processed text → Finalized candidate documents → Relational Database (PostgreSQL)**:
   - Structured documentation is stored for user review and approval.

---

### **2.3 User Review and Submission**
1. **User Interaction**:
   - Nurses access candidate documentation via the **Browser Extension** for review, optional edits, and approval.
   - Edits made by the nurse are processed by the **Human-in-the-Loop Service**, with feedback integrated into the Knowledge Base.
2. **Approved documents → EHR Write Service → EHR API**:
   - Approved documentation is securely submitted to the EHR system.

---

### **2.4 Task Management and Notifications**
1. **Task Generation**:
   - The **Smart Task Manager** retrieves patient care schedules and care plan details from the EHR.
   - Tasks are generated based on urgency, pending actions, and sentiment analysis outcomes.
2. **Notifications**:
   - Nurses receive notifications via the Mobile App for overdue tasks, high-priority issues, or flagged items.

---

### **2.5 Compliance and Audit**
1. **Audit Framework**:
   - All intermediate and final outputs are scanned to replace PII with markup placeholders (e.g., `<patient-name>`).
   - Logs are maintained to track compliance across all data processing stages, using solutions like ELK or CloudWatch (prefer ELK)
   - Data lineage is managed by a dedicated data lineage solutions like OpenLineage, Apache Atlas, or Amundsen
2. **Human-in-the-Loop Interventions**:
   - Log all manual interventions and corrections for traceability.
3. **Finalized Outputs**:
   - Ensure audit trails are complete before submission to external systems (e.g., EHR or analytics platforms).

---

### **2.6 Long-Term Storage and Analytics**
1. **Data Lake Integration**:
   - Finalized and intermediate data, including sentiment analysis and generated documentation, is archived for future AI/ML pipelines and analytics.
2. **AI/ML Enhancements**:
   - Archived data supports continuous improvements, such as refining speaker profiles, enhancing sentiment models, and personalizing documentation.

---
## **3. Dependency Analysis**
This is an analysis of the main system components dependencies.

| **Component**                  | **Dependencies**                                                                                                                                             |
|--------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Frontend Application**       | Relies on the Web Application Service for APIs, EHR Integration for patient data, and HITL Service for exposing correction and feedback APIs.                |
| **Orchestration and Workflow Management** | Depends on all microservices in the data pipeline to trigger workflows and manage retries and fault tolerance.                                            |
| **Audio Ingestion Service**    | Receives audio from the Mobile App and stores enhanced audio in the object store. Provides input to the STT and Sentiment Analysis services.                   |
| **Speech-to-Text (STT) Service** | Uses audio from the Audio Ingestion Service. Feeds raw text to the Initial Text Sanitization Service and HITL Service for corrections.                        |
| **Initial Text Sanitization Service** | Relies on STT outputs for input. Provides sanitized text to Patient Attribution and HITL Service for review and rule refinement.                          |
| **Patient Attribution and Context Construction Service** | Depends on sanitized text from Initial Text Sanitization and metadata from the EHR Integration Service. Provides output to Patient Data Sanitization. |
| **Human-in-the-Loop (HITL) Service** | Interfaces with all data pipeline components for intervention points. Updates Knowledge Base, Compliance Framework, and other downstream components.        |
| **Patient Data Sanitization Service** | Receives reconstructed text streams from the Patient Attribution Service. Outputs sanitized data to Sentiment Analysis and HITL Service for review.        |
| **Knowledge Base Management Service** | Gathers user feedback via HITL Service. Provides templates, rules, and personalized prompts to Documentation Preparation and Sentiment Analysis services.  |
| **Documentation Preparation Service (LLM)** | Depends on sanitized text from Patient Data Sanitization and templates from Knowledge Base. Feeds structured output to Rule-Based Post-Processing.        |
| **Rule-Based Post-Processing** | Uses outputs from Documentation Preparation (LLM) and compliance rules/templates from the Knowledge Base. Feeds validated data to EHR Integration.            |
| **EHR Integration Service**    | Relies on Rule-Based Post-Processing for validated documents and metadata from Patient Attribution. Provides patient schedules to Smart Task Manager.           |
| **Smart Task Manager**         | Pulls patient schedules and care plans from the EHR Integration Service. Integrates with Sentiment Analysis for urgent tasks and flagged items.                |
| **Compliance and Audit Framework** | Monitors all services in the data pipeline for PII/PHI handling and logs human interventions from the HITL Service. Provides immutable logs to the Data Lake. |

---

## **4. Security, Privacy and HIPAA**

### **4.1 Security**
#### Encryption
- All data in transit will use TLS for encryption, while data at rest will use AES-256 encryption.
- Encryption key rotation will follow configurable best practices and utilize a centralized key management system. This can include AWS KMS, Azure Key Vault, or cloud-agnostic solutions such as HashiCorp Vault, with an evaluation of cost-effective virtual or cloud HSM solutions where applicable.

#### Access Control
- Role-Based Access Control (RBAC) will minimize access to APIs and data based on roles and responsibilities.
- Future enhancements will explore zero-trust principles, emphasizing identity verification and network segmentation, provided they do not significantly impact initial timelines.

#### DevSecOps Methodologies
- Security will be integrated into the development lifecycle using the following tools and practices:
  - **Static Application Security Testing (SAST)**: Analyze code for vulnerabilities during development.
  - **Dependency Scanning**: Identify and mitigate vulnerabilities in third-party dependencies.
  - **Runtime Application Self-Protection (RASP)**: Deploy RASP on backend services to monitor and block malicious activity in real-time.
- Comprehensive DevSecOps frameworks such as OWASP SAMM or integrated solutions like Sonatype Nexus, Snyk, or Aqua Security will be considered to meet broad requirements.

#### Additional Measures
- Configure virtual networks (VPCs) to restrict access to required ports and protocols.
- Use container security best practices, including image vulnerability scanning and runtime protection.
- Integrate with intrusion detection and prevention systems to enhance cloud security monitoring.

---

### **4.2 Privacy**

#### Avoiding Long-Term Storage of Patient Identifiable Data
- Patient identifiers will not be stored in long-term storage unless absolutely necessary.
- A secure, ephemeral caching mechanism will store identifiable data temporarily to reduce API call overheads while respecting expiration policies (e.g., 15 minutes, configurable). Redis with encryption and data eviction policies will be a preferred implementation choice.

#### Compliance Framework
- A privacy compliance framework will continuously scan all data to identify and de-identify patient information in accordance with HIPAA Safe Harbor guidelines [1](#ref1).
- Automated audit trails will log every data access, modification, and correction to maintain compliance and enable monitoring.

#### Hierarchical Access Control
- Attribute-Based Access Control (ABAC) will complement RBAC, enabling hierarchical, role-specific access to sensitive data. For example:
  - Customer service engineers: Full data access for operational support.
  - Data scientists: Limited access to anonymized datasets tailored to their needs.

---

### **4.3 Data Retention**

#### Retention Policies
- Define clear retention timelines for different types of data:
  - **Temporary Processing Data**: Dispose within 24 hours.
  - **Operational Logs**: Retain for 30 days for debugging and up to 6 months for compliance audits.
  - **Backups**: Encrypt and retain for 1 year.
- Automated lifecycle management policies will enforce these timelines, with manual policies sufficient during the initial phase.

#### Backup and Recovery
- Backups will be encrypted at rest and designed for reliability, with recovery point objectives (RPOs) and recovery time objectives (RTOs) scoped in later phases.
- Data loss prevention (DLP) systems will enforce backup and recovery policies effectively.

---

### **4.4 Multi-Tenancy**

#### Approach
Multi-tenancy will be implemented using a hybrid model that balances segregation and shared workloads, with the following key components:

1. **Data Segregation**:
   - Each customer will have dedicated databases and object storage, ensuring strong isolation of data.
   - Customer-specific encryption keys will secure access to data, limiting visibility and access to authorized users.

2. **Shared Workloads**:
   - Compute workloads (e.g., microservices, orchestration) will be shared across customers to optimize resource usage and reduce operational overhead.
   - Services accessing customer data will authenticate using customer-specific keys to maintain data segregation.

3. **Infrastructure Configuration**:
   - Workloads will have access to multiple customer VPCs securely through IAM policies and network configurations.
   - Automated provisioning of customer-specific resources will ensure scalability and consistency across deployments.

4. **Advantages**:
   - Combines cost-efficiency of shared workloads with the security of segregated data storage.
   - Reduces complexity compared to fully segregated deployments while ensuring compliance and scalability.

---

## **5. Scalability**
- Designed to handle 10,000+ concurrent users.  
- Modular architecture supports distributed deployments.  

---

### References

<a id="ref1"></a>[1] https://www.hhs.gov/hipaa/for-professionals/special-topics/de-identification/index.html




