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

### **1.11 Documentation Preparation Service (LLM)**
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
   - Logs are maintained to track compliance across all data processing stages.
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

## **3. Security and Privacy**
- **Encryption:** TLS for data in transit, AES-256 for data at rest.  
- **HIPAA Compliance:**  
   - Role-Based Access Control (RBAC).  
   - Comprehensive logging and audit trails.  
   - Data segregation for multi-tenancy.  

---

## **4. Scalability**
- Designed to handle 10,000+ concurrent users.  
- Modular architecture supports distributed deployments.  

---
