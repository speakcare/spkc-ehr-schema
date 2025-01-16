// Thiis running in the context of the page (content script) and is responsible for mapping the chart on the page to a chart name 
// used by the exentension.


// export async function mapChart(tab: Tab): Promise<void> {
export function getPageUrl(): string {
  return window.location.href;
}

export function getPagePath(): string {
    return window.location.pathname;
}


  // Define a type for the chart extraction function
type ChartNameExtractor = () => string | null;

// Define a map that associates paths with chart types and extraction functions
const pathToChartTypeMap: { [key: string]: { formType: string, extractor: ChartNameExtractor } } = {
  '/care/chart/mds/mds.jsp': {
    formType: 'Assessment',
    extractor: extractAssessmentChartName,
  },
  '/care/chart/mds/mdssection.jsp': {
    formType: 'Assessment-Section',
    extractor: extractAssessmentSectionName,
  },
  '/clinical/meddiag/medDiagChart.xhtml': {
    formType: 'Med Diags',
    extractor: extractMedDiagChartName,
  },
  '/care/chart/cp/clientdiag.jsp': {
    formType: 'PatientDiags',
    extractor: extractClientDiagName,
  },
  '/care/chart/cp/clientdiagsheet.jsp': {
    formType: 'PatientDiagSheet',
    extractor: extractClientDiagSheetName,
  },
  '/care/chart/mds/mdsdiagwizardrerank.jsp': {
    formType: 'MedDiagRanking',
    extractor: extractMedDiagRankingName,
  },
  '/clinical/allergy/pop_up/allergyEdit.xhtml': {
    formType: 'Allergy',
    extractor: extractAllergyName,
  },
  '/clinical/lab/popup/newLabReport.xhtml': {
    formType: 'Lab Report',
    extractor: extractLabReportName,
  },
  '/care/chart/ipn/newipn.jsp': {
    formType: 'Progress Note',
    extractor: extractProgressNoteName,
  },
  '/clinical/mds3/sectionlisting.xhtml': {
    formType: 'MDS Summary',
    extractor: extractMDSSummaryName,
  },
  '/clinical/mds3/section.xhtml': { 
    formType: 'MDS Section',
    extractor: extractMDSSectionName,
  },
  '/care/chart/cp/careplandetail_rev.jsp': {
    formType: 'Care Plan',
    extractor: staticCarePlanName,
  },
  '/care/chart/cp/needwizard_rev.jsp': {
    formType: 'Care Plan Focus',
    extractor: staticCarePlanName,
  },
  '/care/chart/cp/neededitcust_rev.jsp': {
    formType: 'Care Plan Custom Focus',
    extractor: staticCarePlanName,
  },
  '/clinical/pho/popup/enhancedOrderEntry/newOrder.xhtml': {
    formType: 'Order New',
    extractor: extractOrderName,
  },
  '/clinical/pho/popup/enhancedOrderEntry/loadOrder.xhtml': {
    formType: 'Order Update',
    extractor: extractOrderName,
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

function extractClientDiagName(): string | null {
    const element = document.querySelector('#sectiontitle');
    return element ? element.textContent?.trim() || null : null;
}

function extractMedDiagChartName(): string | null {
    const element = Array.from(document.querySelectorAll('.pccModuleHeader'))
      .find(el => el.textContent?.includes('Medical Diagnosis'));
    return element ? element.textContent?.trim() || null : null;
}

function extractClientDiagSheetName(): string | null {
    const element = Array.from(document.querySelectorAll('.pccModuleHeader'))
      .find(el => el.textContent?.includes('Edit Diagnosis Sheet'));
    return element ? element.textContent?.trim() || null : null;
}

function extractMedDiagRankingName(): string | null {
    const element = Array.from(document.querySelectorAll('.pccModuleHeader'))
      .find(el => el.textContent?.includes('Medical Diagnosis Ranking'));
    return element ? element.textContent?.trim() || null : null;
}
  
  function extractAllergyName(): string | null {
    const element = document.querySelector('#sectiontitle');
    return element ? element.textContent?.trim() || null : null;
}
  
function extractLabReportName(): string | null {
  const element = document.querySelector('#sectiontitle');
  return element ? element.textContent?.trim() || null : null;
}

function extractProgressNoteName(): string | null {
  const element = document.querySelector('.pccModuleHeader');
  return element ? element.textContent?.trim() || null : null;
}

function extractMDSSummaryName(): string | null {
  const element = document.querySelector('#pagetitle');
  return element ? element.textContent?.trim() || null : null;
}

function extractMDSSectionName(): string | null {
  const element = document.querySelector('#pagetitle');
  return element ? element.textContent?.trim() || null : null;
}

function staticCarePlanName(): string | null {
  return 'Care Plan';
}

function extractOrderName(): string | null {
  const selectElement = document.querySelector('#orderCategoryId');
  const selectedOption = selectElement ? selectElement.querySelector('option[selected]') : null;
  return selectedOption ? selectedOption.textContent?.trim() || null : null;
}


// Function to get the chart type and extractor based on the current page path
export function getChartInfo(): { formType: string, extractor: ChartNameExtractor } | undefined {
  const path = getPagePath();
  return pathToChartTypeMap[path];
}

// Example usage
const chartInfo = getChartInfo();
if (chartInfo) {
  const { formType, extractor } = chartInfo;
  console.log('Current chart type:', formType);
  const chartName = extractor();
  console.log('Extracted chart name:', chartName);
} else {
  console.log('No chart info found for the current path.');
}