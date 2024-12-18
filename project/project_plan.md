### **SpeakCare MVP Development Plan**

---

### **Assumptions**

#### **Team Size and Outsourcing**
1. **Core Team**:
   - 3 internal developers for critical backend services and workflows.
2. **Outsourced Team**:
   - **Browser Extension** and **Mobile / Smartwatch App** development.
   - **DevOps and Infrastructure as Code (IaC)** for cloud deployment.
3. **UX/UI Design**:
   - Initial design for frontend (browser extension and mobile app) to be completed by Week 5.

#### **Critical Priorities**
1. **EHR Integration**: High priority and part of the MVP.
2. **HIPAA Compliance and Security**: Implemented throughout development, with a focus on secure deployment and monitoring.

#### **Scope Adjustments and Simplifications**
1. **Text Sanitization**: Minimal implementation; assume relevant periods are recorded.
2. **Patient Attribution**: Simplified, based on the nurse stating the patient's name at the start of conversations.
3. **Context Construction**: Deferred; assume well-defined recording periods with no interruptions.
4. **Clinical Documentation Conversion**: Simplified; use LLM-only without RAG, GraphRAG, or VectorDB.

---

## **1. Task breaking Down**

### **A. Define the Scope of the MVP**
The MVP will deliver the following key functionalities:
1. **Audio Collection and Ingestion**:
   - Collect audio from the mobile app.
   - Perform noise reduction and segmentation.
   - Convert audio to text with speaker diarization.
2. **Simplified Data Processing**:
   - Perform minimal text sanitization.
   - Conduct basic patient attribution.
3. **Clinical Documentation Generation**:
   - Generate structured documents using LLM.
4. **Frontend Interfaces**:
   - Browser extension for reviewing and approving documents.
   - Mobile app for audio collection and notifications.
5. **EHR Integration**:
   - Fetch patient data (read service).
   - Submit approved documentation (write service).
6. **Centralized User Management**:
   - IDM for internal users.
   - OAuth 2.0 integration for external users (EHR authentication).
7. **DevOps and HIPAA Compliance**:
   - Cloud deployment with monitoring and security practices.

---

### **B. System Deliverable Components Breakdown**

#### **Core Team Responsibilities**
1. **Backend Services**:
   - Audio ingestion (noise reduction and segmentation).
   - Speech-to-text service.
   - Simplified data processing pipeline:
     - Minimal text sanitization.
     - Basic patient attribution.
   - Clinical Documentation Conversion (LLM-only).
2. **EHR Integration**:
   - Read and write services for patient data and documents.
3. **Centralized User Management**:
   - System IDM and OAuth 2.0 integration.
4. **Testing and Debugging**:
   - Ensure HIPAA compliance and security.

#### **Outsourced Responsibilities**
1. **Frontend Development**:
   - Browser extension for document review and approval.
   - Mobile app for audio collection and notifications.
2. **DevOps**:
   - Cloud deployment with IaC (e.g., Terraform).
   - Security practices and monitoring setup.

---

### **C. Tasks Prioritization Based on Dependencies**

| **Priority**         | **Tasks**                                                                          |
|-----------------------|------------------------------------------------------------------------------------|
| **High Priority**     | Audio ingestion, speech-to-text service, clinical documentation conversion (LLM). |
|                       | EHR integration (read/write services).                                            |
|                       | Browser extension (document review/approval).                                     |
|                       | DevOps and HIPAA compliance (IaC and monitoring).                                 |
| **Medium Priority**   | Simplified text sanitization and patient attribution.                             |
|                       | Centralized user management (IDM + OAuth 2.0).                                    |
| **Low Priority**      | Advanced sanitization, context construction, and enhanced clinical documentation. |

---

## **2. Estimated Timelines and Milestones**

### **A. Effort Estimates for Each Task (+Adjustments)**

#### **Adjustments**
1. **Core Team Utilization**: Effort estimates for core team tasks are divided by 0.8 to reflect the 80% utilization factor.  
2. **Project Buffer**: A 15% buffer is applied to the overall timeline after core and outsourced tasks are planned.

#### **Adjusted Table**

| **Component**                        | **Original Effort (Weeks)** | **Adjusted Effort (Weeks)** | **Team**         |
|--------------------------------------|-----------------------------|-----------------------------|------------------|
| **Mobile App**                       | 3                           | 3                           | Outsourced       |
| **Browser Extension**                | 2                           | 2                           | Outsourced       |
| **Audio Ingestion**                  | 3                           | 3.75                        | Core Team        |
| **Speech-to-Text Service**           | 2                           | 2.5                         | Core Team        |
| **Clinical Documentation Conversion**| 4                           | 5                           | Core Team        |
| **EHR Integration (Read/Write)**     | 4                           | 5                           | Core Team        |
| **User Management (IDM + OAuth 2.0)**| 3                           | 3.75                        | Core Team        |
| **DevOps and IaC**                   | 3                           | 3                           | Outsourced       |
| **Testing and Debugging**            | 4                           | 5                           | Core Team + QA   |

---

### **B. Milestones**

#### **Core Team Milestones (Adjusted with Utilization)**

| **Milestone**                | **Tasks**                                                | **Adjusted Timeline** |
|------------------------------|---------------------------------------------------------|------------------------|
| **Milestone 1 (Weeks 1-5)**  | Audio Ingestion, Speech-to-Text Service                 | Weeks 1-5             |
| **Milestone 2 (Weeks 6-11)** | Clinical Documentation Conversion, EHR Integration      | Weeks 6-11            |
| **Milestone 3 (Weeks 12-16)**| Centralized User Management, Backend Testing            | Weeks 12-16           |
| **Milestone 4 (Weeks 17-21)**| Final Testing, HIPAA Compliance, and Deployment         | Weeks 17-21           |

---

#### **Outsourced Milestones**

| **Milestone**                | **Tasks**                                                | **Timeline**       |
|------------------------------|---------------------------------------------------------|--------------------|
| **Milestone 1 (Weeks 1-4)**  | Initial DevOps Setup                                    | Weeks 1-4          |
| **Milestone 2 (Weeks 5-12)** | Browser Extension Development, DevOps Refinement       | Weeks 5-12         |
| **Milestone 3 (Weeks 9-16)** | Final DevOps, Testing for Frontend and Infrastructure   | Weeks 9-16         |

---

### **C. Timeline Proposal for MVP (With Buffer)**

1. **Base Timeline**:  
   - Core tasks finish at **Week 21**.  
   - Outsourced tasks finish at **Week 16**.  

2. **Project Buffer (15%)**:  
   - Adds ~3 weeks to account for unforeseen delays or inefficiencies.  

3. **Final Adjusted Timeline**:  
   - **Overall MVP Completion: Week 24** (6 months).  

| **Phase**                     | **Tasks**                                      | **Adjusted Timeline** |
|-------------------------------|------------------------------------------------|------------------------|
| **Phase 1: Setup and Backend**| Audio ingestion, speech-to-text, DevOps setup  | Weeks 1-5             |
| **Phase 2: Processing**       | Clinical documentation, EHR integration        | Weeks 6-11            |
| **Phase 3: Frontend**         | Browser extension, centralized user management | Weeks 12-16           |
| **Phase 4: Final Testing**    | Testing, compliance, and deployment            | Weeks 17-24           |

---


