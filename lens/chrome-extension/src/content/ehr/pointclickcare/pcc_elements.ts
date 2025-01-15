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
const pathToChartTypeMap: { [key: string]: { chartType: string, extractor: ChartNameExtractor } } = {
  '/care/chart/mds/mds.jsp': {
    chartType: 'Assessment',
    extractor: extractAssessmentChartName,
  },
  '/care/chart/mds/mdssection.jsp': {
    chartType: 'Assessment-Section',
    extractor: extractAssessmentSectionName,
  },
  '/clinical/meddiag/medDiagChart.xhtml': {
    chartType: 'MedDiags',
    extractor: extractMedDiagChartName,
  },
  '/care/chart/cp/clientdiag.jsp': {
    chartType: 'ClientDiags',
    extractor: extractClientDiagName,
  },
  '/care/chart/cp/clientdiagsheet.jsp': {
    chartType: 'ClientDiagSheet',
    extractor: extractClientDiagSheetName,
  },
  '/care/chart/mds/mdsdiagwizardrerank.jsp': {
    chartType: 'MedDiagRanking',
    extractor: extractMedDiagRankingName,
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
  
  

// Function to get the chart type and extractor based on the current page path
export function getChartInfo(): { chartType: string, extractor: ChartNameExtractor } | undefined {
  const path = getPagePath();
  return pathToChartTypeMap[path];
}

// Example usage
const chartInfo = getChartInfo();
if (chartInfo) {
  const { chartType, extractor } = chartInfo;
  console.log('Current chart type:', chartType);
  const chartName = extractor();
  console.log('Extracted chart name:', chartName);
} else {
  console.log('No chart info found for the current path.');
}