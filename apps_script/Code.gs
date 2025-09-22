/**
 * Google Workspace Add-on entry points.
 */

const SUPABASE_URL = PropertiesService.getScriptProperties().getProperty('SUPABASE_URL');
const METADATA_ENDPOINT = `${SUPABASE_URL}/rest/v1/files`;
const FEEDBACK_ENDPOINT = `${SUPABASE_URL}/rest/v1/feedback`;
const WORKER_ENDPOINT = PropertiesService.getScriptProperties().getProperty('WORKER_ENDPOINT');

function getAuthorizationHeader_() {
  const token = PropertiesService.getScriptProperties().getProperty('SERVICE_JWT');
  if (!token) {
    throw new Error('SERVICE_JWT not configured.');
  }
  return `Bearer ${token}`;
}

function buildHomepageCard() {
  return CardService.newCardBuilder()
    .setHeader(CardService.newCardHeader().setTitle('Knowledge Base'))
    .addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newTextParagraph().setText('Select a folder to view metadata and trigger sync.')
        )
    )
    .build();
}

function onHomepage(e) {
  return buildHomepageCard();
}

function showFolderMetadata(e) {
  const drive = e && e.drive ? e.drive : {};
  const item = drive.activeCursorItem || {};
  const driveId = item.id;
  if (!driveId) {
    return CardService.newNavigation().updateCard(buildHomepageCard());
  }

  const metadata = fetchFileMetadata_(driveId);
  const section = CardService.newCardSection()
    .addWidget(CardService.newTextParagraph().setText(`<b>${metadata.title}</b>`))
    .addWidget(CardService.newTextParagraph().setText(`Last reviewed: ${metadata.last_reviewed_at || '—'}`))
    .addWidget(CardService.newTextParagraph().setText(`Core content: ${metadata.core}`));

  const action = CardService.newAction().setFunctionName('handleReindex').setParameters({ driveId });
  section.addWidget(CardService.newTextButton().setText('Re-index').setOnClickAction(action));

  return CardService.newNavigation().updateCard(
    CardService.newCardBuilder()
      .setHeader(CardService.newCardHeader().setTitle(metadata.title))
      .addSection(section)
      .build()
  );
}

function fetchFileMetadata_(driveId) {
  const params = {
    method: 'get',
    headers: {
      Authorization: getAuthorizationHeader_(),
      accept: 'application/json',
    },
    contentType: 'application/json',
    muteHttpExceptions: true,
  };
  const response = UrlFetchApp.fetch(`${METADATA_ENDPOINT}?drive_id=eq.${driveId}`, params);
  if (response.getResponseCode() >= 300) {
    throw new Error(`Failed to load metadata for ${driveId}: ${response.getContentText()}`);
  }
  const data = JSON.parse(response.getContentText());
  return data[0] || { title: 'Unknown', core: false };
}

function handleReindex(e) {
  const driveId = e.parameters.driveId;
  const params = {
    method: 'post',
    headers: {
      Authorization: getAuthorizationHeader_(),
      accept: 'application/json',
    },
    muteHttpExceptions: true,
  };
  const response = UrlFetchApp.fetch(`${WORKER_ENDPOINT}/reindex/${driveId}`, params);
  if (response.getResponseCode() >= 300) {
    const message = response.getContentText();
    const nav = CardService.newNavigation();
    nav.updateCard(
      CardService.newCardBuilder()
        .setHeader(CardService.newCardHeader().setTitle('Re-index failed'))
        .addSection(CardService.newCardSection().addWidget(CardService.newTextParagraph().setText(message)))
        .build()
    );
    return nav;
  }

  return CardService.newNavigation().popCard();
}
