# **SpeakCare System Architecture**

## **Overview**

SpeakCare is an ambient listening system for nurses that captures audio conversations, processes them, and generates structured clinical documentation ready for submission to Electronic Health Records (EHR) systems. The architecture ensures scalability, fault tolerance, and compliance with HIPAA.

---

## **1. System Components**

### **1.1 Frontend Application**
- **Type:** Browser Extension and Mobile Application.  
- **Purpose:** Enables nurses to interact with candidate documentation and receive notifications.  
- **Features:**
  - **Browser Extension**:  
     - View candidate documentation.  
     - Approve and submit documentation to EHR.  
  - **Mobile App**:  
     - Notifications for flagged, incomplete, or pending documents.  
     - Task management.  
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
     - **Audio Ingestion -> STT -> Patient Attribution → Data Sanitation → Clinical Documentation Conversion**.  
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

### **1.6 Patient Attribution Service**
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
    - Outputs patient-specific, reconstructed context streams to the NoSQL Document Database for further processing. 
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

### **1.8 Clinical Documentation Conversion Service**
- **Type:** Microservice.  
- **Purpose:** Converts sanitized text into structured clinical documentation.  
- **Features:**
   - Leverages **LLM Service** to convert text into structured EHR-ready forms.  
   - Integrates with:  
     - **RAG** (Retrieval-Augmented Generation) for contextual data.  
     - **Vector Databases** (e.g., Pinecone, FAISS) for fast, semantic searches.  
   - Enforces JSON schema validation for structured outputs.  
   - Outputs candidate documents to the relational database.  
- **Technologies:**  
   - OpenAI GPT API or equivalent LLM.  
   - RAG/GraphRAG and Vector DB (Pinecone, FAISS).  
   - JSON schema validation for output safety.  

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

### **1.10 Data Storage**
- **Components:**
   - **Object Store**: Temporary storage for audio and raw text.  
   - **NoSQL Document Database**: Stores intermediate text outputs (STT, Patient Attribution, Sanitized Text).  
   - **Relational Database (PostgreSQL)**: Holds candidate documents awaiting user approval.  
   - **Data Lake**: Archives processed data for analytics and future AI/ML pipelines.  

---

### **1.11 Monitoring and Logging**
- **Purpose:** Provides real-time monitoring, logging, and HIPAA audit trails.  
- **Technologies:**  
   - DataDog, ELK Stack (Elasticsearch, Logstash, Kibana), or AWS CloudWatch.  

---

### **1.12 User Management**
- **Purpose:** Centralized authentication and authorization for all users.  
- **Features:**  
   - OAuth 2.0 for secure integration with EHR systems (e.g., PCC).  
   - Role-Based Access Control (RBAC) for internal and external users.  
- **Technologies:**  
   - AWS Cognito, Okta, or equivalent IDM solutions.  

---

### **1.13 Deployment Infrastructure**
- **Components:**
   - **Infrastructure as Code (IaC):** Terraform or CloudFormation.  
   - **Container Orchestration:** Kubernetes for scalable deployments.  
   - **CI/CD Pipelines:** Automated builds, tests, and security scans.  

---

## **2. Core System Flows**

### **2.1 Audio Ingestion to Text Flow**
1. Mobile App → **Audio Ingestion Service** → Audio Enhancement & Noise Reduction.  
2. Enhanced audio → **STT Service** → Text with timestamps and speaker labels → **NoSQL Database**.

---

### **2.2 Data Processing Flow**
1. **Workflow Orchestrator** triggers:  
   - **Patient Attribution → Data Sanitation → Clinical Documentation Conversion**.  
2. Processed text → Finalized candidate documents → **PostgreSQL**.

---

### **2.3 User Review and Submission**
1. Nurses review candidate documents via the **Browser Extension**.  
2. Approved documents → **EHR Write Service** → EHR API.

---

### **2.4 Long-Term Storage and Analytics**
- Processed data and candidate documents → **Data Lake** for future AI/ML pipelines and analytics.

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
