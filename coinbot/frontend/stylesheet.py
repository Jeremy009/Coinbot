STYLE_SHEET = """
    QProgressBar {
        background-color: #DA7B93;
        color: rgb(200, 200, 200);
        border-style: none;
        border-radius: 10px;
        text-align: center;
        font-size: 16px;
    }
    
    QProgressBar::chunk {
        border-radius: 10px;
        background-color: qlineargradient(spread:pad x1:0, x2:1, y1:0.511364, y2:0.523, stop:0 #2E8962, stop:1 #70DDAE);
    }
    
    QTableWidget {
        background-color: transparent;
    }
    
    QTableWidget::item {
        background-color: transparent;
    }
    
    QTableWidget::item:selected { 
        color: black; 
        background-color: rgb(226, 226, 226);
    }
    
    QHeaderView::section {
        background-color: transparent;
    }
    
    QHeaderView {
        background-color: transparent;
    }
"""
