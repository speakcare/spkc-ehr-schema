// Utility to extract form data from the PCC page
export async function extractAssessmentSectionFormFields(): Promise<Record<string, string>> {
  return new Promise((resolve, reject) => {
    if (typeof chrome !== 'undefined' && chrome.scripting && chrome.tabs) {
      chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (tabs.length > 0 && tabs[0].id !== undefined) {
          const activeTabId = tabs[0].id;
          chrome.scripting.executeScript(
            {
              target: { allFrames: false, tabId: activeTabId }, // Target the active tab
              func: () => {
                const form = document.querySelector('form[name="mdsData"]') as HTMLFormElement;
                if (!form) throw new Error("Form not found on the page.");

                const data: Record<string, string> = {};
                const fields = ['ESOLminiToken', 'ESOLclientid', 'ESOLsectioncode', 'ESOLassessid', 'assessClientId'];
                fields.forEach((field) => {
                  const input = form.querySelector(`[name="${field}"]`) as HTMLInputElement;
                  if (input) data[field] = input.value || '';
                });
                return data;
              },
            },
            (results) => {
              if (chrome.runtime.lastError) {
                reject(chrome.runtime.lastError.message);
              } else {
                resolve(results[0]?.result || {});
              }
            }
          );
        } else {
          reject("No active tab found.");
        }
      });
    } else {
      reject("Chrome scripting API not available.");
    }
  });
}


// Function to extract the base URL of the current tab and send a POST request
export async function sendRequestToTabUrl(formData: Record<string, string>) {
  return new Promise((resolve, reject) => {
    chrome.tabs.query({ active: true, currentWindow: true }, async (tabs) => {
      if (tabs.length > 0) {
        try {
          // Get the current tab's URL
          const tabUrl = tabs[0].url;
          if (!tabUrl) {
            throw new Error("Tab URL is undefined.");
          }
          //const baseUrl = new URL(tabUrl).origin + new URL(tabUrl).pathname;
          const baseUrl = new URL(tabUrl)

          // Send the POST request to the base URL
          const response = await fetch(baseUrl, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: new URLSearchParams(formData).toString(),
          });

          if (!response.ok) {
            throw new Error(`Request failed with status: ${response.status}`);
          }

          const responseText = await response.text();
          resolve(responseText);
        } catch (error) {
          reject(error);
        }
      } else {
        reject("No active tab found.");
      }
    });
  });
}

export async function sendSaveRequest(formData: Record<string, string>) {
  try {
    console.log('Sending save request with form data:', formData);
    const response = await fetch(window.location.href, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams(formData).toString(),
    });

    if (!response.ok) {
      console.error('Request failed with status:', response.status);
      throw new Error(`Request failed with status: ${response.status}`);
    }

    const responseText = await response.text();

    return responseText;
  } catch (error: any) {
    throw new Error(`Failed to send request: ${error.message}`);
  }
}
