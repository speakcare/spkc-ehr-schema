```mermaid
flowchart TB
    %% User Interaction
    NurseUser["👩‍⚕️ Nurse User"] --> MobileApp["📱 Mobile App<br>(Bluetooth Audio Collector)"]
    NurseUser --> BrowserExt["💻 Browser Extension<br>(Document Review & Submission)"]

    %% Audio Ingestion
    MobileApp --> AudioStore["🗄️ Audio Storage<br>(Cloud Object Store)"]
    AudioStore --> NoiseReduction["🎛️ Noise Reduction Service"]

    %% Workflow Orchestrator
    Orchestrator["🔗 Workflow Orchestrator<br>(Airflow/Temporal)"] 
    NoiseReduction --> Orchestrator
    Orchestrator --> STT["🗣️ Speech-to-Text Service<br>(Third-Party STT API)"]

    %% Intermediate Text Storage
    STT --> NoSQL["📄 NoSQL Document DB"]
    NoSQL --> PatientAttribution["🔍 Patient Attribution Service"]
    EHRRead["📥 EHR Read Service"] --> PatientAttribution
    PatientAttribution --> NoSQL

    %% Data Sanitation
    PatientAttribution --> DataSanitation["🧹 Data Sanitation Service"]
    EHRRead --> DataSanitation
    DataSanitation --> NoSQL

    %% Clinical Documentation Conversion
    DataSanitation --> LLM["🤖 LLM Service"]
    LLM --> RAG["📚 RAG/GraphRAG<br>(Knowledge Graph)"]
    LLM --> VectorDB["🔎 Vector DB<br>(FAISS/Pinecone)"]
    EHRRead --> RAG

    %% Candidate Documents Workflow
    LLM --> CandidateDocs["📑 Candidate Documents"]
    CandidateDocs --> StructuredDB["🗂️ Structured Database<br>(PostgreSQL)"]
    BrowserExt --> StructuredDB
    BrowserExt --> UserApproval["✅ User Approval<br>(Web Service Backend)"]
    UserApproval --> EHRWrite["📤 EHR Write Service"]
    EHRWrite --> EHRAPI["🛠️ EHR API<br>(PointClickCare)"]

    %% Reading EHR Data
    Orchestrator --> EHRRead
    EHRRead --> StructuredDB

    %% Data Lake for AI/ML and Analytics
    NoSQL --> DataLake["🌊 Data Lake<br>(Long-Term Storage)"]
    CandidateDocs --> DataLake

    %% Data Access to UI
    StructuredDB --> BrowserExt
    CandidateDocs --> Notifications["🔔 Notifications Service"]
    Notifications --> MobileApp

    %% Data Storage and Security
    StructuredDB --> AuditLogs["🔒 Audit Logs"]
    AuditLogs --> SecurityBoundary["🛡️ Security Boundary"]

    %% External Systems and Connections
    subgraph EHR_System["EHR System"]
        EHRAPI
    end

    subgraph DataStorage["Data Storage"]
        StructuredDB
        NoSQL
        AuditLogs
        DataLake
    end

    subgraph CloudServices["Cloud Services"]
        AudioStore
        NoiseReduction
        STT
        PatientAttribution
        DataSanitation
        Orchestrator
        LLM
        RAG
        VectorDB
    end

    subgraph UserInterface["User Interaction"]
        BrowserExt
        Notifications
    end
