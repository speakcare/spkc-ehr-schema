// Thiis running in the context of the page (content script) and is responsible for mapping the chart on the page to a chart name 
// used by the exentension.

import { getPagePath } from '../../../utils/url_utills';

// export function getPageUrl(): string {
//   return window.location.href;
// }

// export function getPagePath(): string {
//     return window.location.pathname;
// }

// Define a type for the chart extraction function
type ChartNameExtractor = () => string | null;
type UsernameExtractor = () => string | null;
type OrgnameExtractor = () => string | null;

export interface ChartParser {
  chartType: string;
  chartNameExtractor: ChartNameExtractor;
  usernameExtractor: UsernameExtractor;
  orgCodeExtractor: OrgnameExtractor;
}

export interface ChartInfo {
  chartType: string;
  chartName: string;
  username: string;
  orgCode: string;
}

export function getChartParser(path?: string): 
ChartParser | null {

  const pagePath = path ? path : getPagePath();
  if (!pagePath) {
    return null;
  }

  if (pagePath in pathToChartTypeMap) {
    return pathToChartTypeMap[pagePath];
  }

  // Find the first match where the key is a prefix of the path
  for (const key in pathToChartTypeMap) {
    if (pagePath.startsWith(key)) {
      return pathToChartTypeMap[key];
    }
  }

  return null;
}

export function parseChart(): ChartInfo | null {
  const parser = getChartParser();
  if (!parser) {
    return null;
  }

  const chartName = parser.chartNameExtractor();
  const username = parser.usernameExtractor();
  const orgCode = parser.orgCodeExtractor();

  if (!chartName || !username || !orgCode) {
    return null;
  }

  const sanitizedChartType = parser.chartType.replace(/\s+/g, '_');
  const sanitizedChartName = chartName.replace(/\s+/g, '_');


  return {
    chartType: sanitizedChartType,
    chartName: sanitizedChartName,
    username,
    orgCode,
  };
} 


/******************************* 
* Page elements extraction functions
********************************/
function extractUsernameFromLabel(): string | null {
  // get the username from the userLabel element
  const userLabelElement = document.querySelector('.userLabel');
  return userLabelElement ? userLabelElement.textContent?.trim() || null : null;
}



function extractUsernameFromPccUsageAnalytics(): string | null {
  const htmlContent = document.documentElement.outerHTML;

  // Step 1: Find the specific <script> tag containing "PccUsageAnalytics.config"
  const scriptRegex = /<script>([\s\S]*?PccUsageAnalytics\.config[\s\S]*?)<\/script>/;
  const scriptMatch = htmlContent.match(scriptRegex);
  
  if (scriptMatch) {
    const scriptContent = scriptMatch[1]; // Extract the content of the script tag
  
    // Step 2: Extract the account-id value from the script content
    const accountIdRegex = /PccUsageAnalytics\.config\['account-id'\]\s*=\s*"([^"]+)"/;
    const accountIdMatch = scriptContent.match(accountIdRegex);

    const userIdRegex = /PccUsageAnalytics\.config\['user-id'\]\s*=\s*"([^"]+)"/;
    const userIdMatch = scriptContent.match(userIdRegex);

    if (!userIdMatch || !accountIdMatch) {
      console.log(`extractUsernameFromPccUsageAnalytics: failed to extract userIdMatch: ${userIdMatch}, accountIdMatch: ${accountIdMatch}`);
      return null;
    } 

    const userId = userIdMatch[1];
    const accountId = accountIdMatch[1];

    if (userId.startsWith(`${accountId}.`)) {
      return userId.substring(accountId.length + 1);
    }
    else {
      console.log(`extractUsernameFromPccUsageAnalytics: userId ${userId} does not start with ${accountId}.: `);
      return null;
    }
  } else {
    console.log('Target <script> tag not found.');
    return null;
  }
}


function extractOrgCodeFromPccUsageAnalytics(): string | null {
  const htmlContent = document.documentElement.outerHTML;

  // Step 1: Find the specific <script> tag containing "PccUsageAnalytics.config"
  const scriptRegex = /<script>([\s\S]*?PccUsageAnalytics\.config[\s\S]*?)<\/script>/;
  const scriptMatch = htmlContent.match(scriptRegex);
  
  if (scriptMatch) {
    const scriptContent = scriptMatch[1]; // Extract the content of the script tag
  
    // Step 2: Extract the account-id value from the script content
    const accountIdRegex = /PccUsageAnalytics\.config\['account-id'\]\s*=\s*"([^"]+)"/;
    const accountIdMatch = scriptContent.match(accountIdRegex);
  
    if (accountIdMatch) {
      const accountId = accountIdMatch[1]; // Extracted account-id
      console.log(`Extracted account-id: ${accountId}`);
      return accountId;
    } else {
      console.log('extractOrgCodeFromPccUsageAnalytics: account-id not found in the script.');
      return null;
    }
  } else {
    console.log('Target <script> tag not found.');
    return null;
  }
}


function extractOrgCodeFromDSIFeedback(): string | null {
  const scriptContent = document.querySelector('script[type="text/javascript"]')?.textContent;
  if (!scriptContent) return null;

  const orgCodeMatch = scriptContent.match(/orgCode:\s*"([^"]+)"/);
  return orgCodeMatch ? orgCodeMatch[1] : null;
}


// Define a map that associates paths with chart types and extraction functions
const pathToChartTypeMap: { [key: string]: { chartType: string, chartNameExtractor: ChartNameExtractor, usernameExtractor: UsernameExtractor, orgCodeExtractor: OrgnameExtractor } } = {
  '/care/chart/mds/mds.jsp': {
    chartType: 'Clinical Assessment',
    chartNameExtractor: extractAssessmentChartName,
    usernameExtractor: extractUsernameFromLabel,
    orgCodeExtractor: extractOrgCodeFromDSIFeedback,
  },
  '/care/chart/mds/mdssection.jsp': {
    chartType: 'Clinical Assessment',
    chartNameExtractor: extractAssessmentSectionName,
    usernameExtractor: extractUsernameFromLabel,
    orgCodeExtractor: extractOrgCodeFromDSIFeedback,
  },
  '/clinical/meddiag/medDiagChart.xhtml': {
    chartType: 'Med Diags',
    chartNameExtractor: getDiagnosisName,
    usernameExtractor: extractUsernameFromLabel,
    orgCodeExtractor: extractOrgCodeFromPccUsageAnalytics
  },
  '/care/chart/cp/clientdiag.jsp': {
    chartType: 'PatientDiags',
    chartNameExtractor: getDiagnosisName,
    usernameExtractor: extractUsernameFromPccUsageAnalytics,
    orgCodeExtractor: extractOrgCodeFromPccUsageAnalytics,
  },
  '/care/chart/cp/clientdiagsheet.jsp': {
    chartType: 'PatientDiagSheet',
    chartNameExtractor: getDiagnosisName,
    usernameExtractor: extractUsernameFromPccUsageAnalytics,
    orgCodeExtractor: extractOrgCodeFromPccUsageAnalytics,
  },
  '/care/chart/mds/mdsdiagwizardrerank.jsp': {
    chartType: 'MedDiagRanking',
    chartNameExtractor: getDiagnosisName,
    usernameExtractor: extractUsernameFromPccUsageAnalytics,
    orgCodeExtractor: extractOrgCodeFromPccUsageAnalytics,
  },
  '/clinical/allergy/pop_up/allergyEdit.xhtml': {
    chartType: 'Allergy',
    chartNameExtractor: getAllergyName,
    usernameExtractor: extractUsernameFromPccUsageAnalytics,
    orgCodeExtractor: extractOrgCodeFromPccUsageAnalytics,
  },
  '/clinical/lab/popup/newLabReport.xhtml': {
    chartType: 'Lab Report',
    chartNameExtractor: getLabReportName,
    usernameExtractor: extractUsernameFromPccUsageAnalytics,
    orgCodeExtractor: extractOrgCodeFromPccUsageAnalytics,
  },
  '/clinical/radiology/popup/newRadiologyReport.xhtml': {
    chartType: 'Radiology Report',
    chartNameExtractor: getRadiologyReportName,
    usernameExtractor: extractUsernameFromPccUsageAnalytics,
    orgCodeExtractor: extractOrgCodeFromPccUsageAnalytics,
  },
  '/care/chart/ipn/newipn.jsp': {
    chartType: 'Progress Note',
    chartNameExtractor: getProgressNoteName,
    usernameExtractor: extractUsernameFromPccUsageAnalytics,
    orgCodeExtractor: extractOrgCodeFromPccUsageAnalytics,
  },
  '/clinical/mds3/sectionlisting.xhtml': {
    chartType: 'MDS Summary',
    chartNameExtractor: getMDSSummaryName,
    usernameExtractor: extractUsernameFromLabel,
    orgCodeExtractor: extractOrgCodeFromDSIFeedback,
  },
  '/clinical/mds3/section.xhtml': { 
    chartType: 'MDS Section',
    chartNameExtractor: extractMDSSectionName,
    usernameExtractor: extractUsernameFromLabel,
    orgCodeExtractor: extractOrgCodeFromDSIFeedback,
  },
  '/clinical/mds3_popup/': {
    chartType: 'MDS Popup',
    chartNameExtractor: extractMDS3PopupTitle,
    usernameExtractor: extractUsernameFromPccUsageAnalytics,
    orgCodeExtractor: extractOrgCodeFromPccUsageAnalytics,
  },
  '/clinical/mdskardex_popup/mdskardexresponse.xhtml':{
    chartType: 'MDS Kardex',
    chartNameExtractor: extractMDS3PopupTitle,
    usernameExtractor: extractUsernameFromPccUsageAnalytics,
    orgCodeExtractor: extractOrgCodeFromPccUsageAnalytics
  },
  '/care/chart/cp/careplandetail_rev.jsp': {
    chartType: 'Care Plan',
    chartNameExtractor: getCarePlanName,
    usernameExtractor: extractUsernameFromLabel,
    orgCodeExtractor: extractOrgCodeFromDSIFeedback,
  },
  '/care/chart/cp/needwizard_rev.jsp': {
    chartType: 'Care Plan Focus',
    chartNameExtractor: getCarePlanName,
    usernameExtractor: extractUsernameFromPccUsageAnalytics,
    orgCodeExtractor: extractOrgCodeFromPccUsageAnalytics,
  },
  '/care/chart/cp/neededitcust_rev.jsp': {
    chartType: 'Care Plan Custom Focus',
    chartNameExtractor: getCarePlanName,
    usernameExtractor: extractUsernameFromPccUsageAnalytics,
    orgCodeExtractor: extractOrgCodeFromPccUsageAnalytics,
  },
  '/clinical/pho/popup/enhancedOrderEntry/newOrder.xhtml': {
    chartType: 'Order New',
    chartNameExtractor: extractOrderName,
    usernameExtractor: extractUsernameFromPccUsageAnalytics,
    orgCodeExtractor: extractOrgCodeFromPccUsageAnalytics,
  },
  '/clinical/pho/popup/enhancedOrderEntry/loadOrder.xhtml': {
    chartType: 'Order Update',
    chartNameExtractor: extractOrderName,
    usernameExtractor: extractUsernameFromPccUsageAnalytics,
    orgCodeExtractor: extractOrgCodeFromPccUsageAnalytics,
  },
  '/care/chart/wandv/editclientvitals.jsp': {
    chartType: 'Vitals',
    chartNameExtractor: getVitalsName,
    usernameExtractor: extractUsernameFromPccUsageAnalytics,
    orgCodeExtractor: extractOrgCodeFromPccUsageAnalytics,
  },
  '/care/chart/wandv/editbaselinevitals.jsp': {
    chartType: 'Vitals Baseline',
    chartNameExtractor: getVitalsBaselineName,
    usernameExtractor: extractUsernameFromPccUsageAnalytics,
    orgCodeExtractor: extractOrgCodeFromPccUsageAnalytics,
  },
  '/clinical/immunedisplay.xhtml': {
    chartType: 'Immunization',
    chartNameExtractor: getImmunName,
    usernameExtractor: extractUsernameFromLabel,
    orgCodeExtractor: extractOrgCodeFromDSIFeedback,
  },
  // Add more mappings as needed
};

// Example extraction functions

function extractAssessmentChartName(): string | null {
    const element = document.querySelector('.pageTitle');
    return element ? element.textContent?.trim() || null : null;
}


function extractAssessmentSectionName(): string | null {
    return document.title || null;
}


function getDiagnosisName(): string | null {
  return "Diagnosis";
}
  
function getAllergyName(): string | null {
    return "Allergy";
}
  
function getLabReportName(): string | null {
  return "Lab Report";
}

function getRadiologyReportName(): string | null {
  return "Radiology Report";
}


function getProgressNoteName(): string | null {
  return "Progress Note";
}

function getMDSSummaryName(): string | null {
  return "MDS Summary";
}

function getMDSPopupName(): string | null {
  return "MDS Popup";
}

function extractMDS3PopupTitle(): string | null {
  const titleElement = document.querySelector('title');
  if (titleElement) {
    const chartName = titleElement.textContent?.trim();
    return chartName || null;
  }
  return null;
}

function extractMDSSectionName(): string | null {
  const element = document.querySelector('#pagetitle');
  return element ? element.textContent?.trim() || null : null;
}

function getCarePlanName(): string | null {
  return 'Care Plan';
}

function getVitalsName(): string | null {
  return 'Vitals';
}
function getVitalsBaselineName(): string | null {
  return 'Vitals Baseline';
}

function getImmunName(): string | null {
  return 'Immunization';
}

function extractOrderName(): string | null {
  const selectElement = document.querySelector('#orderCategoryId');
  const selectedOption = selectElement ? selectElement.querySelector('option[selected]') : null;
  return selectedOption ? selectedOption.textContent?.trim() || null : null;
}

// Alon-To-Do (Sep09-2025)

// Clinical -> EMAR -> 
// How much time they spend on each TAB (Mar/Tar / etc)