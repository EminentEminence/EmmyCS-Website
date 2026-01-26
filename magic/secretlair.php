<!DOCTYPE html>
<html lang="en">
<head>
    <!-- Bootstrap CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>

    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Secret Lairs</title>
    <style>
        .mtgcard {
            transition: transform 0.2s; /* Animation */
        }
        .mtgcard:hover {
            transform: scale(1.2);
        }
    </style>
</head>
<body>

<div class="container">  
    <h1>Custom Secret Lairs</h1>

    <?php

    $baseDir = __DIR__ . '/cards/Secret Lairs';
    $baseUrl = 'cards/Secret Lairs';
    $allowedExtensions = ['jpg', 'jpeg', 'png', 'webp', 'gif'];

    // Get all subfolders (each is a lair)
    $folders = array_filter(scandir($baseDir), function ($item) use ($baseDir) {
        return $item !== '.' && $item !== '..' && is_dir($baseDir . '/' . $item);
    });

    foreach ($folders as $folderName) {
        $folderPath = $baseDir . '/' . $folderName;
        $folderUrl  = $baseUrl . '/' . rawurlencode($folderName);

        // Optional: Add a description if you want
        echo "<h2> ----- " . htmlspecialchars($folderName) . " ----- </h2>\n";

        // Get images
        $files = array_filter(scandir($folderPath), function ($file) use ($folderPath, $allowedExtensions) {
            if ($file === '.' || $file === '..') return false;
            $ext = strtolower(pathinfo($file, PATHINFO_EXTENSION));
            return in_array($ext, $allowedExtensions) && is_file($folderPath . '/' . $file);
        });

        // Sort files alphabetically
        sort($files);

        echo '<div class="row">';
        foreach ($files as $file) {
            $imgSrc = $folderUrl . '/' . rawurlencode($file);
            $alt = pathinfo($file, PATHINFO_FILENAME);
            $cardName = urlencode($alt);
            $imgPath = urldecode($imgSrc);
            $imgFsPath = __DIR__ . '/' . $imgPath;
            $imgVersion = file_exists($imgFsPath) ? filemtime($imgFsPath) : time();
            echo <<<HTML
            <div class="col-6 col-md-4 col-lg-2 mb-3">
                <a href="cardview.php?name={$cardName}&folder={$folderUrl}">
            HTML;
            echo "<img class=\"mtgcard img-fluid\" src=\"" .$imgPath . "?v=" . $imgVersion ."\" alt=\"" . htmlspecialchars($alt) . "\">\n";
            echo <<<HTML
                </a>
            </div>
            HTML;
        }
        echo '</div><hr>'; // Separate sections
    }
    ?>
</div>

</body>
</html>
