import importlib
import logging

from config import CONFIG

logger = logging.getLogger("customLogger")

def create_class_from_string(module_path, class_name_str, *args, **kwargs):
    """
    Dynamically imports a module and instantiates a class from it.

    Args:
        module_path (str): The dot-separated path to the module (e.g., "subfolder.my_module").
        class_name_str (str): The name of the class as a string (e.g., "MyDynamicClass").
        *args, **kwargs: Arguments to pass to the class's __init__ method.

    Returns:
        An instance of the specified class, or None if not found/imported.
    """
    try:
        # Import the module dynamically
        module = importlib.import_module(module_path)

        # Get the class object from the module using its string name
        class_obj = getattr(module, class_name_str)

        # Instantiate the class
        instance = class_obj(*args, **kwargs)
        return instance
    except (ImportError, AttributeError) as e:
        print(f"Error creating class: {e}")
        return None

def sites_from_config(search_list, app_configs: CONFIG):
    sites = []
    for tracker in search_list:
        try:
            class_name = tracker.upper()
            my_instance = create_class_from_string(f"trackers.{class_name}", class_name,  app_configs)
            if my_instance:
                sites.append(my_instance)
                # print(await my_instance.get_cat_id("MOVIE"))
            else:
                print(f"Invalid tracker name {tracker}")
                logger.error(f"Invalid tracker name {tracker}")

            # MyClass exists and is assigned to the_class
        except AttributeError as e:
            print(f"Error: {e}")
    return sites

def get_video_type(source, modifier):
    if not isinstance(source, list):
        source = (source or '').lower()
    else:
        # add better check here instead of first item.
        source = source[0].lower()
    if not isinstance(modifier, list):
        modifier = (modifier or '').lower()
    else:
        index_element = next((i for i, v in enumerate(modifier) if v.lower() == "remux"), None)
        if index_element != None:
            modifier = modifier[index_element].lower()
        else:
            index_element = next((i for i, v in enumerate(modifier) if v.lower() == "rip"), None)
            if index_element != None:
                modifier = modifier[index_element].lower()

    if source == 'bluray':
        if modifier == 'remux':
            return 'REMUX'
        elif modifier == 'full':
            return 'FULL DISC'
        else:
            return 'ENCODE'
    elif source == 'dvd':
        if modifier == 'remux':
            return 'REMUX'
        elif modifier == 'full':
            return 'FULL DISC'
        elif modifier == 'Rip':
            return 'ENCODE'
        else:
            return 'ENCODE'
    elif source in ['webdl', 'web-dl']:
        return 'WEB-DL'
    elif source in ['webrip', 'web-rip']:
        return 'WEBRIP'
    elif source == 'hdtv':
        return 'HDTV'
    # sonarr types
    elif source == "web" and "webdl" in modifier:
        return 'WEB-DL'
    elif "remux" in modifier:
        return 'REMUX'
    elif "hdtv" in modifier:
        return 'HDTV'
    elif "bluray" in modifier and "remux" not in modifier:
        return 'ENCODE'
    else:
        return 'OTHER'