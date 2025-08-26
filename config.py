"""
基金可视化系统配置文件
"""

# 数据库配置
DATABASE_PATH = "fund_data.db"

# 特殊产品配置
SPECIAL_PRODUCTS_CONFIG = {
    "瑞幸1号": {
        "data_source_type": "custom_csv",
        "data_path": r"Z:\Administrator\Desktop\交易数据导出\Stock",
        "file_pattern": "Account-{date}_{time}.csv",
        "total_asset_column": "总资产"
    }
}

# 应用配置
APP_TITLE = "基金投资组合可视化系统"
APP_ICON = "📈"

# 页面配置
PAGE_CONFIG = {
    "page_title": APP_TITLE,
    "page_icon": APP_ICON,
    "layout": "wide",
    "initial_sidebar_state": "expanded"
}

# 支持的文件格式
SUPPORTED_FILE_FORMATS = ['.csv', '.xlsx', '.xls']

# 主要指数代码
MAJOR_INDICES = {
    "沪深300": "000300",
    "中证500": "000905",
    "中证1000": "000852",
    "中证2000": "932000"
}

# 数据表列名映射
COLUMN_MAPPING = {
    # 净值数据列名
    'nav_columns': {
        'date': ['日期', 'Date', 'date'],
        'nav_value': ['单位净值', '净值', 'NAV', 'nav_value', '单位净值'],
        'cumulative_nav': ['累计净值', '累积净值', 'Cumulative NAV', 'cumulative_nav']
    },
    # 持仓数据列名
    'holdings_columns': {
        'date': ['日期', 'Date', 'date'],
        'stock_code': ['股票代码', '证券代码', 'Stock Code', 'stock_code', '代码'],
        'stock_name': ['股票名称', '证券名称', 'Stock Name', 'stock_name', '名称'],
        'position_ratio': ['持仓比例', '占比', 'Position Ratio', 'position_ratio', '比例'],
        'market_value': ['市值', '持仓市值', 'Market Value', 'market_value'],
        'shares': ['持股数量', '股数', 'Shares', 'shares', '数量']
    }
}