import requests
from bs4 import BeautifulSoup
import re

WAN_TO_YUAN = 10000  # 1万元 = 10000元


def fetch_houses():
    """从5i5j网站爬取民族大学附近的二手房信息"""
    url = r"https://bj.5i5j.com/ershoufang/r3/_%E6%B0%91%E6%97%8F%E5%A4%A7%E5%AD%A6/"
    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        ),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Connection': 'keep-alive',
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.encoding = 'utf-8'
    except requests.RequestException as e:
        print(f"网络请求失败：{e}")
        return []

    soup = BeautifulSoup(response.text, 'lxml')

    houses = []

    # 获取主列表区域
    house_list = soup.find('ul', id='houseList')
    if house_list is None:
        house_list = soup.find('ul', class_=re.compile(r'list_ol'))
    if house_list is None:
        # 尝试直接找所有列表项
        all_li = soup.find_all('li', class_=re.compile(r'fl_con|list-item|house'))
    else:
        all_li = house_list.find_all('li', recursive=False)

    # 遇到"为你推荐"分隔项后，停止处理后续条目
    for li in all_li:
        li_text = li.get_text()
        # 遇到"为你推荐"标记则停止（含分隔行自身）
        if '为你推荐' in li_text:
            break

        # 提取房屋名称（标题）
        name = None
        title_tag = li.find('h2')
        if title_tag:
            a_tag = title_tag.find('a')
            name = (a_tag or title_tag).get_text(strip=True)
        if not name:
            a_tag = li.find('a', class_=re.compile(r'title|name|house'))
            if a_tag:
                name = a_tag.get_text(strip=True)

        if not name:
            continue

        # 提取面积（平米）
        area = None
        area_pattern = re.compile(r'(\d+\.?\d*)\s*平米?')
        # 先查找包含面积的span/p/dd
        for tag in li.find_all(['span', 'p', 'dd', 'em']):
            text = tag.get_text(strip=True)
            m = area_pattern.search(text)
            if m:
                area_val = float(m.group(1))
                # 过滤掉明显不是面积的数字（面积一般在20~1000平米之间）
                if 20 <= area_val <= 1000:
                    area = area_val
                    break
        if area is None:
            m = area_pattern.search(li_text)
            if m:
                area_val = float(m.group(1))
                if 20 <= area_val <= 1000:
                    area = area_val

        # 提取总价（万元）
        total_price = None
        # 查找含有"万"字的元素
        for tag in li.find_all(['strong', 'span', 'em', 'b', 'p', 'dd']):
            text = tag.get_text(strip=True)
            m = re.search(r'(\d+\.?\d*)\s*万?$', text)
            if m and '万' in text:
                total_price = float(m.group(1))
                break
            # 某些页面总价直接是数字，后跟"万"在父标签文本里
            m2 = re.search(r'^(\d+\.?\d*)$', text)
            if m2:
                parent_text = tag.parent.get_text(strip=True) if tag.parent else ''
                if '万' in parent_text and '元' not in tag.get_text():
                    candidate = float(m2.group(1))
                    # 总价一般在10~10000万之间
                    if 10 <= candidate <= 10000:
                        total_price = candidate
                        break

        # 提取单价（元/平米）
        unit_price = None
        unit_pattern = re.compile(r'(\d+\.?\d*)\s*元\s*/?\s*平')
        for tag in li.find_all(['span', 'p', 'dd', 'em', 'div']):
            text = tag.get_text(strip=True)
            m = unit_pattern.search(text)
            if m:
                unit_price = float(m.group(1))
                break
        if unit_price is None:
            m = unit_pattern.search(li_text)
            if m:
                unit_price = float(m.group(1))

        # 如果面积和总价都有，可以反推单价（或反推总价）
        if unit_price is None and area and total_price:
            unit_price = round(total_price * WAN_TO_YUAN / area, 0)
        if total_price is None and area and unit_price:
            total_price = round(unit_price * area / WAN_TO_YUAN, 2)

        if name and area is not None and unit_price is not None and total_price is not None:
            houses.append({
                '名称': name,
                '面积': area,        # 单位：平米（float）
                '单价': unit_price,  # 单位：元/平米（float）
                '总价': total_price, # 单位：万元（float）
            })

    return houses


def str_width(s):
    """计算字符串的显示宽度（中文字符占2个位置）"""
    width = 0
    for ch in s:
        if ord(ch) > 0x7F:
            width += 2
        else:
            width += 1
    return width


def ljust_cn(s, width):
    """按显示宽度左对齐填充（兼容中文字符）"""
    pad = width - str_width(s)
    return s + ' ' * max(pad, 0)


def display_houses(houses, sort_key, reverse=False):
    """整齐显示房屋信息"""
    if not houses:
        print("暂无数据。")
        return

    key_map = {
        '1': '名称',
        '2': '面积',
        '3': '单价',
        '4': '总价',
    }
    field = key_map.get(sort_key, '名称')
    sorted_houses = sorted(houses, key=lambda x: x[field], reverse=reverse)

    order_str = "降序" if reverse else "升序"
    print(f"\n按【{field}】{order_str}排列：")

    name_width = 30  # 名称列显示宽度
    sep = "-" * 76
    header_name = ljust_cn('名称', name_width)
    print(sep)
    print(f"{'序号':>4}  {header_name}  {'面积(平米)':>10}  {'单价(元/平)':>11}  {'总价(万元)':>9}")
    print(sep)
    for i, h in enumerate(sorted_houses, 1):
        name_cell = ljust_cn(h['名称'], name_width)
        print(
            f"{i:>4}  {name_cell}  "
            f"{h['面积']:>10.1f}  "
            f"{h['单价']:>11.0f}  "
            f"{h['总价']:>9.2f}"
        )
    print(sep)
    print(f"共 {len(sorted_houses)} 条记录\n")


def show_menu():
    """显示排序菜单"""
    print("=" * 40)
    print("  排序菜单")
    print("  1：按名称排序")
    print("  2：按面积排序")
    print("  3：按单价排序")
    print("  4：按总价排序")
    print("  S：升序（默认）")
    print("  J：降序")
    print("  Q：退出")
    print("=" * 40)


def main():
    print("正在爬取民族大学附近二手房信息，请稍候...")
    houses = fetch_houses()

    if not houses:
        print("未能获取房屋数据，请检查网络连接或网站是否可访问。")
        return

    print(f"成功获取 {len(houses)} 条房源信息。")

    sort_key = '1'    # 默认按名称排序
    reverse = False   # 默认升序

    while True:
        show_menu()
        choice = input("请输入选项：").strip().upper()

        if choice == 'Q':
            print("程序退出。")
            break
        elif choice in ('1', '2', '3', '4'):
            sort_key = choice
            display_houses(houses, sort_key, reverse)
        elif choice == 'S':
            reverse = False
            print("已切换为升序。")
            display_houses(houses, sort_key, reverse)
        elif choice == 'J':
            reverse = True
            print("已切换为降序。")
            display_houses(houses, sort_key, reverse)
        else:
            print("无效输入，请重新选择。")


if __name__ == '__main__':
    main()
