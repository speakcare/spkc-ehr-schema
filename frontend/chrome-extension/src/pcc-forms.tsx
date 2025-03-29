import React from 'react';

export interface PccQuesionOption {
  option?: string;
  pcc_id?: string;
  [key: string]: number | string | undefined;
}

export interface PccQuestion {
  question: string;
  pcc_id?: string;
  type: 'single_select' | 'multiple_select' | 'checkbox' | 'textarea';
  options?: PccQuesionOption[];
}

export enum PccQuestionType {
  SingleSelect = 'single_select',
  MultipleSelect = 'multiple_select',
  Checkbox = 'checkbox',
  Textarea = 'textarea',
}


export interface PccAssessmentResponse {
  responses: Array<{
    table_name: string;
    sections: {
      [key: string]: {
        fields: {
          [key: string]: string | string[] | boolean;
        };
      };
    };
  }>;
}

export const fallRiskSection1Form: PccQuestion[] = [
  {
    "question": "LEVEL OF CONSCIOUSNESS/ MENTAL STATUS",
    "pcc_id": "Cust_A_1",
    "type": PccQuestionType.SingleSelect,
    "options": [
      {"Alert (0 points)": 0},
      {"DISORIENTED at all times (2 points)": 2},
      {"INTERMITTENT CONFUSION (4 points)": 4},
      {"COMATOSE (0 points)": 0}
    ]
  },
  {
    "question": "HISTORY OF FALLS (Past 3 Months)",
    "pcc_id": "Cust_B_2",
    "type": PccQuestionType.SingleSelect,
    "options": [
      {"NO FALLS in past 3 months (0 points)": 0},
      {"1 - 2 FALLS in past 3 months (2 points)": 2},
      {"3 OR MORE FALLS in past 3 months (4 points)": 4}
    ]
  },
  {
    "question": "URINE ELIMINATION STATUS",
    "pcc_id": "Cust_C_3",
    "type": PccQuestionType.SingleSelect,
    "options": [
      {"REGULARLY CONTINENT (0 points)": 0},
      {"REQUIRES REGULAR ASSISTANCE WITH ELIMINATION (2 points)": 2},
      {"REGULARLY INCONTINENT (4 points)": 4}
    ]
  },
  {
    "question": "VISION STATUS",
    "pcc_id": "Cust_D_4",
    "type": PccQuestionType.SingleSelect,
    "options": [
      {"ADEQUATE (with or without glasses) (0 points)": 0},
      {"POOR (with or without glasses) (2 points)": 2},
      {"LEGALLY BLIND (4 points)": 4}
    ]
  },
  {
    "question": "GAIT/BALANCE/AMBULATION",
    "type": PccQuestionType.MultipleSelect,
    "options": [
      {
        "option": "Gait/Balance normal (0 points)",
        "pcc_id": "Cust_E_5",
      },
      {
        "option": "Balance problem while standing/walking (1 point)",
        "pcc_id": "Cust_E_6",
      },
      {
        "option": "Decreased muscular coordination/jerking movements (1 point)",
        "pcc_id": "Cust_E_7",
      },
      {
        "option": "Change in gait pattern when walking (i.e. shuffling) (1 point)",
        "pcc_id": "Cust_E_8",
      },
      {
        "option": "Requires use of assistive devices (1 point)",
        "pcc_id": "Cust_E_9",
      },
      {
        "option": "N/A - not able to perform (2 points)",
        "pcc_id": "Cust_E_10",
      }
    ]
  },
  {
    "question": "MEDICATIONS",
    "type": PccQuestionType.SingleSelect,
    "pcc_id": "Cust_F_11",
    "options": [
      {"NONE of these medications taken currently or within last 7 days (0 points)": 0},
      {"TAKES 1-2 of these medications currently and/or within last 7 days (2 points)": 2},
      {"TAKES 3-4 of these medications currently and/or within last 7 days (4 points)": 4}
    ]
  },
  {
    "question": "MEDICATIONS CHANGES",
    "type": PccQuestionType.Checkbox,
    "pcc_id": "Cust_F_12",
  },
  {
    "question": "PREDISPOSING DISEASES",
    "type": PccQuestionType.SingleSelect,
    "pcc_id": "Cust_G_13",
    "options": [
      {"NONE PRESENT (0 points)": 0},
      {"1 - 2 PRESENT (2 points)": 2},
      {"3 OR MORE PRESENT (4 points)": 4}
    ]
  },
  {
    "question": "PREDISPOSING DISEASES - comments",
    "type": PccQuestionType.Textarea,
    "pcc_id": "Cust_G_14",
  }
];

// Generate PCC form data from the response
// Only fill in the fields that are present in the response
// If the field is not present, it will not be added to the form data so that it will not override the existing data
export const generatePccFormData = (response: PccAssessmentResponse) => {
  const formData: Record<string, string> = {
    ESOLsaveflag: 'SONLY',
    ESOLsavedUDASaveFlag: 'N'
  };

  // Get the Fall Risk Screen section from response
  const fallRiskSection = response.responses.find(
    (r) => r.table_name === "Fall Risk Screen"
  )?.sections["Fall Risk Screen: SECTION 1"]?.fields;

  if (!fallRiskSection) {
    throw new Error("No Fall Risk Screen data found in response");
  }

  fallRiskSection1Form.forEach(question => {
    const responseValue = fallRiskSection[question.question];
    if (!responseValue) return;

    
    switch (question.type) {
      case PccQuestionType.SingleSelect:
        // Find the matching option and get its numeric value
        if (question.options && question.pcc_id) {
          const matchingOption = question.options.find(option => 
            Object.keys(option)[0] === responseValue
          );
          if (matchingOption) {
            const numericValue = Object.values(matchingOption)[0];
            if (typeof numericValue === 'number') {
              // Add acknowledgment field
              formData[`ack${question.pcc_id}`] = 'Y';
              formData[question.pcc_id] = numericValue.toString();
            }
          }
        }
        break;

      case PccQuestionType.MultipleSelect:
        // Handle array of selected options
        if (Array.isArray(responseValue) && question.options) {
          question.options.forEach((option) => {
            if (option.pcc_id && option.option && responseValue.includes(option.option)) {
              // Add acknowledgment field
              formData[`ack${option.pcc_id}`] = 'Y';
              formData[option.pcc_id] = '1';
              formData[`chk${option.pcc_id}`] = 'on';
            }
          });
        }
        break;

      case PccQuestionType.Checkbox:
        if (responseValue === true && question.pcc_id) {
          formData[`ack${question.pcc_id}`] = 'Y';
          formData[question.pcc_id] = '1';
          formData[`chk${question.pcc_id}`] = 'on';
        } 
        break;

      case PccQuestionType.Textarea:
        if (question.pcc_id) {
          formData[`ack${question.pcc_id}`] = 'Y';
          formData[question.pcc_id] = responseValue as string;
        }
        break;
    }
  });
  console.debug('PCC form data:', formData);
  return formData;
}; 