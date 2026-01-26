<?php
// --- Validate URL parameters ---
if (!isset($_GET['name']) || !isset($_GET['folder'])) {
    die("Folder or card not specified.");
}

// Decode URL parameters
$folderName = rawurldecode($_GET['folder']);
$cardName   = trim(rawurldecode($_GET['name']));

// --- Paths relative to this PHP file ---
$folderPath = __DIR__ .'/' . $folderName;
$cardDataFile = $folderPath . '/cardData.txt';

// --- Check folder exists ---
if (!is_dir($folderPath)) {
    die("Folder '$folderName' not found at $folderPath");
}

// --- Allowed image extensions ---
$allowedExtensions = ['jpg','jpeg','png','webp','gif'];

// --- Find the card image ---
$cardFile = null;
foreach (scandir($folderPath) as $file) {
    if ($file === '.' || $file === '..') continue;

    $ext = strtolower(pathinfo($file, PATHINFO_EXTENSION));
    $nameWithoutExt = pathinfo($file, PATHINFO_FILENAME);

    if (in_array($ext, $allowedExtensions) && $nameWithoutExt === $cardName) {
        // Build relative path for browser
        $cardFile = rawurlencode($folderName) . '/' . rawurlencode($file);
        break;
    }
}

if (!$cardFile) {
    die("Card '$cardName' not found in folder '$folderName'.");
}

// --- Load card data from cardData.txt ---

$cards = [];
$logFile = __DIR__ . '/cardview.log';

// Helper function to append to the log
function logMessage($message) {
    global $logFile;
    $time = date('Y-m-d H:i:s');
    file_put_contents($logFile, "[$time] $message\n", FILE_APPEND);
}

// Log start
logMessage("Starting to read cardData.txt from folder: $folderName");

// Check if file exists
if (!file_exists($cardDataFile)) {
    logMessage("cardData.txt not found: $cardDataFile");
} else {
    if (($handle = fopen($cardDataFile, 'r')) !== false) {
        // Read header
        $header = fgetcsv($handle, 0, "\t");
        logMessage("Header row read: " . implode(' | ', $header));

        $rowCount = 0;
        while (($data = fgetcsv($handle, 0, "\t")) !== false) {
            $rowCount++;
            if (count(array_filter($data)) === 0) {
                logMessage("Skipping empty row #$rowCount");
                continue;
            }

            $card = [];
            foreach ($header as $index => $colName) {
                $card[$colName] = isset($data[$index]) ? $data[$index] : null;
            }

            // Log first card
            if ($rowCount === 1) logMessage("First card parsed: " . $card['Name'] ?? 'Unknown');

            if (!empty($card['Name'])) {
                $card['Name'] = str_replace("'", "", str_replace(',', '', $card['Name'])); // Clean commas and apostrophes
                logMessage("Processing card #$rowCount: " . $card['Name']);
                $cards[$card['Name']] = $card;
                logMessage("Added card: " . $card['Name']);
            }


        }



        fclose($handle);
        logMessage("Finished reading cardData.txt, total rows processed: $rowCount");
    } else {
        logMessage("Failed to open cardData.txt for reading.");
    }
}

// --- Get the current card's details ---
$cardName = trim($cardName);
$cardDetails = $cards[$cardName] ?? null;
if ($cardDetails) {
    logMessage("Loaded card details for: $cardName");
} else {
    logMessage("Card not found in data: $cardName");
}

$rulesText   = $cardDetails['Rules Text'] ?? '';
$rulesText = str_replace('\\n', "\n", $rulesText);
$flavorText  = $cardDetails['Flavor Text'] ?? '';
$manaCost    = $cardDetails['Mana Cost'] ?? '';
$type        = $cardDetails['Type'] ?? '';
$rarity      = $cardDetails['Rarity'] ?? '';
$power       = $cardDetails['Power'] ?? '';
$toughness   = $cardDetails['Toughness'] ?? '';
$loyalty     = $cardDetails['Loyalty'] ?? '';
$illustrator = $cardDetails['Illustrator'] ?? '';
$cardNumber  = $cardDetails['CardNumber'] ?? '';
$notes       = $cardDetails['Notes'] ?? '';


?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title><?php echo htmlspecialchars($cardName); ?></title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    
    <style>
        p {
            font-size:1.5em;
        }
    </style>
</head>
<body>
<div class="container mt-4">
    <h1><?php echo htmlspecialchars($cardName); ?></h1>
    <div class="row">
        <div class="col-12 col-md-6">
            <img class="mtgcard img-fluid" src="<?php echo urldecode($cardFile); ?>?v=<?php echo filemtime(__DIR__ . '/' . urldecode($cardFile)); ?>" alt="<?php echo htmlspecialchars($cardName); ?>">
        </div>
        <div class="col-12 col-md-6 card-details">

            <?php if (!empty($type)): ?>
                <p><strong>Type:</strong> <?= htmlspecialchars($type) ?></p>
            <?php endif; ?>

            <?php if (!empty($manaCost)): ?>
                <p><strong>Mana Cost:</strong> <?= htmlspecialchars($manaCost) ?></p>
            <?php endif; ?>

            <?php if (!empty($rarity)): ?>
                <p><strong>Rarity:</strong> <?= htmlspecialchars($rarity) ?></p>
            <?php endif; ?>

            <?php if (!empty($power) || !empty($toughness)): ?>
                <p>
                    <strong>Power/Toughness:</strong>
                    <?= htmlspecialchars($power ?: '–') ?>/<?= htmlspecialchars($toughness ?: '–') ?>
                </p>
            <?php endif; ?>

            <?php if (!empty($loyalty)): ?>
                <p><strong>Loyalty:</strong> <?= htmlspecialchars($loyalty) ?></p>
            <?php endif; ?>

            <?php if (!empty($illustrator)): ?>
                <p style="display:inline" ><strong>Illustrator:</strong> <?= htmlspecialchars($illustrator) ?></p>
                <p>(If you are either not credited or want your art taken down, pls contact.)</p>
            <?php endif; ?>

            <?php if (!empty($rulesText)): ?>
                <p>
                    <strong>Rules Text:</strong><br>
                    <?= nl2br(htmlspecialchars($rulesText)) ?>
                </p>
            <?php endif; ?>

            <?php if (!empty($flavorText)): ?>
                <p>
                    <strong>Flavor Text:</strong><br>
                    <em><?= nl2br(htmlspecialchars($flavorText)) ?></em>
                </p>
            <?php endif; ?>

            <?php if (!empty($notes)): ?>
                <p><strong>Notes:</strong> <?= htmlspecialchars($notes) ?></p>
            <?php endif; ?>

        </div>

    </div>
    <a href="#" class="btn btn-primary mt-3" onclick="if (history.length > 1) { history.back(); } else { window.location.href='magic.emmycs.co.uk'; } return false;">Back</a>
    <div class = "row">
    <h2> ----- Some other cards from the set ----- </h2>
    <?php
        $counter = 0;
        foreach ($cards as $newCardName => $cardData) {
            $cardFile = rawurlencode($folderName) . '/' . rawurlencode($newCardName);
            // Skip the current card
            if ($newCardName === $cardName) continue;
            if ($counter >= 6) break; // Show only 6 other cards
            
            echo "<div class=\"col-6 col-md-4 col-lg-2 mb-3\">\n";
            echo "    <a href=\"cardview.php?name=" . urlencode($newCardName) . "&folder=" . rawurlencode($folderName) . "\">\n";
            echo "        <img class=\"mtgcard img-fluid\" src=\"" . urldecode($cardFile) . ".png?v=" . filemtime(__DIR__ . '/' . urldecode($cardFile) . ".png") . "\" alt=\"" . htmlspecialchars($newCardName) . "\">\n";

            echo "    </a>\n";
            echo "</div>\n";
            $counter = $counter + 1;
        }
    ?>
</div>
</body>
</html>