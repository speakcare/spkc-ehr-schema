const apiKey = 'AIzaSyDN9AU2YmH0vDqpOcAsANHKBPHWVPiOhCg';
const spreadsheetId = '1KHjVFQ-sQmyfI3GM4W5jdmu0k4tAXeQ2EpIcLMMLlY4';
const range = 'Sheet1!A1';  // Starting cell for data

export async function testGoogleSheets() {
    fetch(`https://sheets.googleapis.com/v4/spreadsheets/${spreadsheetId}?key=${apiKey}`)
        .then(response => response.json())
        .then(data => {
            const sheets = data.sheets.map((sheet: any) => sheet.properties.title);
            console.log('Existing sheets:', sheets);

            // Step 2: Check if 'Sheet1' exists
            if (sheets.includes('Sheet1')) {
            writeToSheet();
            } else {
            createSheetAndWrite();
            }
        })
        .catch(error => {
            console.error('Error fetching sheet info:', error);
        });
}


// Function to write to an existing sheet
function writeToSheet() {
  const range = 'Sheet1!A1';
  fetch(`https://sheets.googleapis.com/v4/spreadsheets/${spreadsheetId}/values/${range}?valueInputOption=RAW&key=${apiKey}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      values: [
        ['Name', 'Age'],
        ['Alice', '25'],
        ['Bob', '30']
      ]
    })
  })
  .then(response => response.json())
  .then(data => {
    console.log('Data written successfully:', data);
  })
  .catch(error => {
    console.error('Error writing to sheet:', error);
  });
}

// Function to create a new sheet and then write data
function createSheetAndWrite() {
  fetch(`https://sheets.googleapis.com/v4/spreadsheets/${spreadsheetId}:batchUpdate?key=${apiKey}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      requests: [{
        addSheet: {
          properties: { title: 'Sheet1' }
        }
      }]
    })
  })
  .then(response => response.json())
  .then(() => {
    console.log('Sheet1 created successfully.');
    writeToSheet();  // Now write to the newly created sheet
  })
  .catch(error => {
    console.error('Error creating new sheet:', error);
  });
}

